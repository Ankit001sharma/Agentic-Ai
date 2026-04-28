"""SupervisorAgent — Nemotron-first ReAct or legacy parallel crew + optional ReAct."""

from __future__ import annotations

import asyncio
import json
import time

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm import vllm_state
from app.llm.litellm_client import CompletionWithToolsResult, acomplete_with_tools
from app.agents.parsers.react_json import parse_react_json
from app.agents.prompts.nemotron_supervisor import NEMOTRON_SUPERVISOR_SYSTEM
from app.agents.specialists import intent, multimodal, threat_investigation
from app.agents.memory import episodic
from app.agents.tools.registry import dispatch, get_supervisor_openai_tools
from app.schemas.sentinel import ScanState

log = get_logger("agent.supervisor")

_LEGACY_SYSTEM = (
    "You are Sentinel-X supervisor. Use tools to investigate the user request. "
    "Call delegate_to_intent, delegate_to_threat, delegate_to_multimodal first (parallel allowed). "
    "Then delegate_to_policy. Only call emit_explanation_card when you have enough evidence — "
    "it must include verdict, confidence, headline, user_facing_message, primary_reason."
)


async def run_parallel_crew(state: ScanState) -> None:
    """Run Intent + Threat + Multimodal in parallel; populate blackboard."""
    await asyncio.gather(
        intent.run(state),
        threat_investigation.run(state),
        multimodal.run(state),
    )


async def run_react_loop_legacy(state: ScanState) -> None:
    """Optional narrow ReAct (severity gate + short loop), previous behavior."""
    s = get_settings()
    prelim = max((f.severity for f in state.findings), default=0.0)
    if not s.vllm_base_url or prelim < 0.25 or prelim > 0.85:
        return
    messages: list[dict] = [
        {"role": "system", "content": _LEGACY_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "prompt_preview": (state.prompt or "")[:2000],
                    "risk": state.risk,
                    "findings_count": len(state.findings),
                }
            ),
        },
    ]
    tools = get_supervisor_openai_tools()
    for step in range(min(3, s.max_supervisor_steps)):
        t0 = time.perf_counter()
        res: CompletionWithToolsResult = await acomplete_with_tools(
            messages=messages,
            tools=tools,
            model=s.vllm_planner_model,
            max_tokens=400,
        )
        model_used = res.model_used or s.vllm_planner_model
        if res.tool_calls:
            for tc in res.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                out = await dispatch(tc.name, args, state)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                state.agent_steps.append(
                    {
                        "phase": "supervisor_react_legacy",
                        "step": step,
                        "tool": tc.name,
                        "observation": out.summary[:2000],
                        "latency_ms": latency_ms,
                        "model_used": model_used,
                    }
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": tc.arguments},
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": out.summary[:4000],
                    }
                )
                if tc.name == "emit_explanation_card":
                    state.explanation_draft = args
                    return
            continue
        parsed = parse_react_json(res.text or "")
        if parsed and parsed.final:
            state.explanation_draft = parsed.final
            state.agent_steps.append(
                {
                    "phase": "supervisor_react_legacy_json",
                    "step": step,
                    "tool": "emit_explanation_card",
                    "observation": "final_json",
                    "model_used": model_used,
                }
            )
            return
        if parsed and parsed.tool:
            out = await dispatch(parsed.tool, parsed.args, state)
            state.agent_steps.append(
                {
                    "phase": "supervisor_react_legacy_json",
                    "step": step,
                    "tool": parsed.tool,
                    "observation": out.summary[:2000],
                    "model_used": model_used,
                }
            )
            if parsed.tool == "emit_explanation_card":
                state.explanation_draft = parsed.args
                return
        break


async def run_react_loop_primary(state: ScanState, *, memory_context: str) -> None:
    """Nemotron-first: full tool loop until steps exhausted or emit_explanation_card."""
    s = get_settings()
    if not s.vllm_base_url:
        return
    messages: list[dict] = [
        {"role": "system", "content": NEMOTRON_SUPERVISOR_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "prompt_preview": (state.prompt or "")[:2000],
                    "risk": state.risk,
                    "findings_count": len(state.findings),
                    "historical_risk": state.user.historical_risk,
                    "memory_similar_incidents": memory_context[:6000],
                }
            ),
        },
    ]
    tools = get_supervisor_openai_tools()
    max_steps = max(1, s.supervisor_max_steps)
    for step in range(max_steps):
        t0 = time.perf_counter()
        res: CompletionWithToolsResult = await acomplete_with_tools(
            messages=messages,
            tools=tools,
            model=s.vllm_planner_model,
            max_tokens=700,
        )
        model_used = res.model_used or s.vllm_planner_model
        if res.tool_calls:
            for tc in res.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                out = await dispatch(tc.name, args, state)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                state.agent_steps.append(
                    {
                        "phase": "nemotron_supervisor",
                        "step": step,
                        "tool": tc.name,
                        "observation": out.summary[:2000],
                        "latency_ms": latency_ms,
                        "model_used": model_used,
                    }
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": tc.arguments},
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": out.summary[:4000],
                    }
                )
                if tc.name == "emit_explanation_card":
                    state.explanation_draft = args
                    return
            continue
        parsed = parse_react_json(res.text or "")
        if parsed and parsed.final:
            state.explanation_draft = parsed.final
            state.agent_steps.append(
                {
                    "phase": "nemotron_supervisor_json",
                    "step": step,
                    "tool": "emit_explanation_card",
                    "observation": "final_json",
                    "model_used": model_used,
                }
            )
            return
        if parsed and parsed.tool:
            out = await dispatch(parsed.tool, parsed.args, state)
            state.agent_steps.append(
                {
                    "phase": "nemotron_supervisor_json",
                    "step": step,
                    "tool": parsed.tool,
                    "observation": out.summary[:2000],
                    "model_used": model_used,
                }
            )
            if parsed.tool == "emit_explanation_card":
                state.explanation_draft = parsed.args
                return
            continue
        break


async def run(state: ScanState) -> ScanState:
    """Prescan (optional) + Nemotron-first ReAct or legacy parallel crew."""
    s = get_settings()
    mode = (s.supervisor_mode or "react_primary").strip().lower()

    if mode == "legacy_parallel_crew":
        await run_parallel_crew(state)
        state.agent_steps.append(
            {
                "phase": "supervisor",
                "tool": "parallel_crew",
                "observation": f"findings={len(state.findings)} intent={state.intent}",
            }
        )
        try:
            if vllm_state.vllm_healthy or s.vllm_base_url:
                await run_react_loop_legacy(state)
        except Exception as e:  # noqa: BLE001
            log.warning("supervisor_react_legacy_skipped", error=str(e))
        return state

    # react_primary (Nemotron-first)
    prescan = (s.agent_prescan or "full_threat").strip().lower()
    if prescan == "full_threat":
        from app.agents import threat

        await threat.run(state)
        state.agent_steps.append(
            {
                "phase": "prescan",
                "tool": "full_threat",
                "observation": f"findings={len(state.findings)}",
            }
        )
    elif prescan == "minimal":
        await run_parallel_crew(state)
        state.agent_steps.append(
            {
                "phase": "prescan",
                "tool": "minimal_parallel_crew",
                "observation": f"findings={len(state.findings)} intent={state.intent}",
            }
        )
    else:
        state.agent_steps.append(
            {
                "phase": "prescan",
                "tool": "none",
                "observation": "no_deterministic_prescan",
            }
        )

    try:
        mem_rows = await episodic.recall_similar_incidents_vector(
            state.prompt or "",
            k=max(1, s.memory_recall_top_k),
        )
        memory_blob = json.dumps(mem_rows)[:6000]
    except Exception as e:  # noqa: BLE001
        log.warning("memory_context_failed", error=str(e))
        memory_blob = "[]"

    try:
        if s.vllm_base_url:
            await run_react_loop_primary(state, memory_context=memory_blob)
    except Exception as e:  # noqa: BLE001
        log.warning("nemotron_supervisor_skipped", error=str(e))

    state.agent_steps.append(
        {
            "phase": "supervisor",
            "tool": "nemotron_complete",
            "observation": f"findings={len(state.findings)} intent={state.intent}",
        }
    )
    return state
