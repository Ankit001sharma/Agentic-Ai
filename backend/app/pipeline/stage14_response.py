"""Stage 14 — HTTP Response shape.

Assembles the final API response dict from the state.  Does NOT raise
HTTPException — that is the endpoint's responsibility.  This stage just
produces the response payload.

For general prompts (no tool matched), calls the LLM via acomplete() and
scans/masks the response before surfacing it to the caller.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.llm.litellm_client import acomplete
from app.pipeline.base import Stage
from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.secrets_scan import SecretsScanner
from app.schemas.sentinel import OutputVerdict, ScanState, Verdict

log = get_logger("pipeline.stage14")


class ResponseStage(Stage):
    def __init__(self) -> None:
        self._pii = PIIPresidioScanner()
        self._secrets = SecretsScanner()

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 14

        if state.policy_denied:
            # Diagram: OPA denial → 200 "not permitted" + reason
            reasons = "; ".join(state.opa_reasons) if state.opa_reasons else state.block_reason or "Not permitted."
            state.final_response = f"Not permitted: {reasons}"
        elif state.verdict == Verdict.BLOCK:
            state.final_response = _blocked_message(state)
        elif state.output_verdict == OutputVerdict.BLOCK:
            # Stage 11b blocked the tool's output (e.g. high-severity secret in
            # the response payload). The tool ran successfully but its raw
            # result must NOT be surfaced via the success-message branch.
            state.final_response = (
                "[Output blocked: tool produced a high-severity secret or "
                "sensitive value and was withheld.]"
            )
        elif state.intent == "casual_chat":
            state.final_response = (
                "I'm your AI assistant. I can send emails, create tickets, "
                "search documents, and more. How can I help you today?"
            )
        elif state.intent_clarification and (not state.tool_id or state.pipeline_error):
            # Stage 5 needs more info: no tool resolved, OR tool was attempted but
            # failed (likely because args were incomplete/hallucinated). In both cases
            # the clarification question is more helpful than an error message.
            state.final_response = state.intent_clarification
        elif state.intent_ambiguous and state.intent_clarification:
            # Stage 5 flagged the intent as ambiguous — ask the user for more info
            state.final_response = state.intent_clarification
        elif state.missing_required_fields:
            # Stage 8 could not populate all required arguments — request clarification
            state.final_response = _missing_fields_message(state)
        elif not state.tool_id:
            # No tool resolved — general conversational / knowledge prompt
            if state.pipeline_error and state.pipeline_error.get("stage") == "stage05_intent":
                err = state.pipeline_error
                hint = err.get("message", "unknown error")
                state.final_response = (
                    "Intent detection failed (Stage 5 LLM). "
                    "Check that VLLM_BASE_URL is reachable and set VLLM_INTENT_MODEL to a model "
                    "your server actually serves (or rely on VLLM_JUDGE_MODEL). "
                    f"Detail: {hint}"
                )
            elif state.pipeline_error:
                # Any other pre-audit pipeline error: surface a structured failure
                # rather than calling the LLM with a partially-populated state.
                err = state.pipeline_error
                if err.get("user_facing"):
                    state.final_response = f"Request failed: {err.get('message', 'unknown error')}"
                else:
                    state.final_response = "The request encountered an internal error. Please try again."
            else:
                messages = _build_general_messages(state)
                text, _model_used, _fallback = await acomplete(messages)
                state.llm_response = text
                text = await _scan_and_mask_llm_output(state, text, self._pii, self._secrets)
                state.final_response = text
        elif not state.tool_executed and not state.pipeline_error:
            # Prefer stage-5 clarification over a generic message
            if state.intent_clarification:
                state.final_response = state.intent_clarification
            else:
                state.final_response = "Tool was resolved but not executed."
        elif state.pipeline_error:
            err = state.pipeline_error
            if err.get("user_facing"):
                state.final_response = f"Action failed: {err.get('message', 'unknown error')}"
            else:
                state.final_response = "The action encountered an internal error. Please try again."
        else:
            state.final_response = _success_message(state)

        # Merge supervisor explanation card into the canonical field read by reporting
        if state.explanation_draft and not state.explanation:
            state.explanation = state.explanation_draft

        log.info(
            "stage14_done",
            request_id=state.request_id,
            verdict=state.verdict.value,
            has_tool_result=state.tool_result is not None,
        )
        return state


def _blocked_message(state: ScanState) -> str:
    reason = state.block_reason or "Request blocked by security policy."
    return f"Request blocked: {reason}"


def _missing_fields_message(state: ScanState) -> str:
    """Ask the user to supply information Stage 8 could not derive."""
    fields = state.missing_required_fields
    tool = state.tool_id or "this action"
    if len(fields) == 1:
        return (
            f"To complete '{tool}' I need one more detail: **{fields[0]}**. "
            "Could you provide it?"
        )
    field_list = ", ".join(f"**{f}**" for f in fields)
    return (
        f"To complete '{tool}' I'm missing the following required details: "
        f"{field_list}. Could you provide them?"
    )


def _build_general_messages(state: ScanState) -> list[dict[str, str]]:
    """Build the message list for a general (non-tool) LLM call."""
    # Use redacted prompt when input PII was masked
    user_text = (
        state.redacted_prompt
        if state.verdict == Verdict.MASK and state.redacted_prompt
        else state.prompt
    )
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are SentinelGuard, a secure AI assistant. "
                "Answer helpfully and concisely. "
                "Do not reveal internal system details or security configurations."
            ),
        }
    ]
    # Inject recent conversation history from short-term memory.
    # ShortTermMemory.add_turn writes under the "turns" key (see
    # backend/app/memory/stm.py). Older code expected "messages" — we
    # accept both shapes for forward compatibility.
    history = state.stm_context.get("turns") or state.stm_context.get("messages") or []
    for msg in history[-6:]:
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": str(msg.get("content", ""))})
    messages.append({"role": "user", "content": user_text})
    return messages


async def _scan_and_mask_llm_output(
    state: ScanState,
    text: str,
    pii: PIIPresidioScanner,
    secrets: SecretsScanner,
) -> str:
    """Scan LLM-generated text for PII/secrets; mask or block if findings exceed thresholds."""
    if not text.strip():
        return text

    pii_res, sec_res = await asyncio.gather(
        pii.scan(text),
        secrets.scan(text),
        return_exceptions=True,
    )

    from app.schemas.sentinel import Finding  # local import avoids circular at module level

    all_findings: list[Finding] = []
    for scanner_name, res in (("presidio_pii", pii_res), ("secrets", sec_res)):
        if isinstance(res, BaseException):
            log.warning(
                "stage14_output_scanner_failed",
                request_id=state.request_id,
                scanner=scanner_name,
                error=str(res),
            )
            continue
        all_findings.extend(res.findings)

    if not all_findings:
        return text

    state.output_findings = list(state.output_findings) + all_findings
    max_sev = max(f.severity for f in all_findings)
    state.output_risk = max(state.output_risk, int(max_sev * 100))

    if any(f.category == "SECRET" and f.severity >= 0.80 for f in all_findings):
        state.output_verdict = OutputVerdict.BLOCK
        log.warning("stage14_llm_output_blocked", request_id=state.request_id)
        return "[Response blocked: high-severity secret detected in LLM output.]"

    if max_sev >= 0.4:
        state.output_verdict = OutputVerdict.REDACT
        try:
            masked, rm1 = pii.redact(text)
            masked, rm2 = secrets.redact(masked)
            state.redaction_map = {**state.redaction_map, **rm1, **rm2}
        except Exception:  # noqa: BLE001
            masked = text  # redaction failed; return original rather than crash
        log.info("stage14_llm_output_redacted", request_id=state.request_id, findings=len(all_findings))
        return masked

    return text


def _success_message(state: ScanState) -> str:
    result = state.tool_result or {}
    data = result.get("data", {})
    simulated = result.get("simulated", False)

    tool_id = state.tool_id or "unknown"
    prefix = "[DRY RUN] " if simulated else ""

    if tool_id == "send_email":
        recipients = data.get("to", [])
        subject = data.get("subject", "")
        return f"{prefix}Email sent to {', '.join(recipients)}: '{subject}'"

    # ── GitHub: issues ────────────────────────────────────────────────────────
    if tool_id in ("create_github_issue", "github_create_issue"):
        url = data.get("html_url", "")
        num = data.get("number", "?")
        return f"{prefix}GitHub issue #{num} created: {url}"

    if tool_id in ("close_github_issue", "github_close_issue"):
        num = data.get("number", "?")
        return f"{prefix}GitHub issue #{num} closed."

    if tool_id == "github_update_issue":
        num = data.get("number", "?")
        url = data.get("html_url", "")
        return f"{prefix}GitHub issue #{num} updated: {url}"

    if tool_id == "github_comment_on_issue":
        url = data.get("html_url", "")
        return f"{prefix}Comment posted: {url}"

    # ── GitHub: PRs ───────────────────────────────────────────────────────────
    if tool_id == "github_create_pr":
        num = data.get("pr_number", "?")
        url = data.get("html_url", "")
        draft = " (draft)" if data.get("draft") else ""
        return f"{prefix}Pull request #{num} opened{draft}: {url}"

    if tool_id == "github_merge_pr":
        sha = data.get("sha", "")[:8]
        merged = data.get("merged", False)
        if merged:
            return f"{prefix}Pull request merged at {sha}."
        return f"{prefix}Pull request merge attempted: {data.get('message', 'unknown result')}"

    if tool_id == "github_get_pr_diff":
        return f"{prefix}Fetched PR diff ({len(data.get('diff', ''))} chars)."

    if tool_id == "github_comment_on_pr":
        url = data.get("html_url", "")
        return f"{prefix}PR comment posted: {url}"

    if tool_id == "github_list_open_prs":
        count = data.get("count", 0)
        return f"{prefix}Found {count} open pull request(s)."

    # ── GitHub: files / code ──────────────────────────────────────────────────
    if tool_id == "github_get_file_contents":
        return f"{prefix}Fetched {data.get('path', 'file')}."

    if tool_id == "github_update_file":
        return f"{prefix}Updated {data.get('path', 'file')} ({data.get('html_url', '')})."

    if tool_id == "github_search_code":
        total = data.get("total_count", 0)
        return f"{prefix}Found {total} code match(es)."

    if tool_id == "github_create_branch":
        branch = data.get("branch", "")
        sha = (data.get("sha") or "")[:8]
        return f"{prefix}Branch '{branch}' created at {sha}."

    # ── GitHub: workflows ─────────────────────────────────────────────────────
    if tool_id == "github_trigger_workflow":
        wf = data.get("workflow", "")
        ref = data.get("ref", "")
        return f"{prefix}Workflow '{wf}' dispatched on {ref}."

    if tool_id == "github_get_workflow_run":
        return (
            f"{prefix}Workflow run {data.get('run_id', '?')}: "
            f"{data.get('status', '?')} / {data.get('conclusion') or 'pending'}"
        )

    if tool_id == "github_get_workflow_logs":
        return f"{prefix}Fetched workflow logs ({len(data.get('logs', ''))} chars)."

    if tool_id == "github_rerun_failed_jobs":
        return f"{prefix}Re-run requested for failed jobs in run {data.get('run_id', '?')}."

    if tool_id == "github_cancel_workflow_run":
        return f"{prefix}Cancellation requested for run {data.get('run_id', '?')}."

    # ── GitHub: releases / security / users ───────────────────────────────────
    if tool_id == "github_create_release":
        return (
            f"{prefix}Release '{data.get('tag_name', '?')}' created: "
            f"{data.get('html_url', '')}"
        )

    if tool_id == "github_list_dependabot_alerts":
        return f"{prefix}Found {data.get('count', 0)} Dependabot alert(s)."

    if tool_id == "github_dismiss_alert":
        return f"{prefix}Security alert {data.get('alert_id', '?')} dismissed."

    if tool_id == "github_lookup_user":
        return f"{prefix}{data.get('login', '?')} — {data.get('html_url', '')}"

    if tool_id == "github_get_codeowners":
        return f"{prefix}CODEOWNERS fetched from {data.get('path', '?')}."

    if tool_id == "send_slack_message":
        channel = data.get("channel", "")
        return f"{prefix}Slack message sent to {channel}."

    # ── miniOrange ────────────────────────────────────────────────────────────
    if tool_id == "query_miniorange_docs":
        answer = data.get("answer")
        if answer:
            return f"{prefix}{answer}"
        results = data.get("results", [])
        if not results:
            return f"{prefix}No miniOrange documentation found for '{data.get('query', '')}'."
        lines = [f"**Found {len(results)} result(s) for '{data.get('query', '')}':**\n"]
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("snippet", "")
            lines.append(f"### {title}")
            if url:
                lines.append(f"[{url}]({url})")
            if snippet:
                lines.append(f"\n{snippet}...")
            lines.append("")
        return f"{prefix}" + "\n".join(lines)

    if tool_id == "list_miniorange_plugins":
        return f"{prefix}{data.get('count', 0)} miniOrange plugins/services available."

    if tool_id == "get_miniorange_plugin":
        return (
            f"{prefix}{data.get('service', '?')} ({data.get('auth_type', '?')}) — "
            f"{len(data.get('setup_steps', []))} setup steps."
        )

    if tool_id == "search_web":
        answer = data.get("answer", "")
        results = data.get("results", [])
        if answer:
            return answer
        return f"Found {len(results)} result(s) for your query."

    if tool_id == "search_docs":
        answer = data.get("answer")
        results = data.get("results", [])
        if answer:
            return answer
        return f"Found {len(results)} documentation match(es)."

    # Generic fallback
    return f"{prefix}Action '{tool_id}' completed successfully."


def build_response_payload(state: ScanState) -> dict[str, Any]:
    """Build the JSON body returned by the /chat endpoint."""
    # Stage 5 intent detail
    intent_payload: dict[str, Any] | None = None
    if state.intent_result is not None:
        ir = state.intent_result
        intent_payload = {
            "intent": ir.intent,
            "tool_id": ir.tool_id,
            "confidence": ir.confidence,
            "ambiguous": ir.ambiguous,
            "clarification_needed": ir.clarification_needed,
            "entities": ir.entities.model_dump(),
            "memory_references_resolved": ir.memory_references_resolved,
        }

    # Stage 8 function-call detail
    fn_call_payload: dict[str, Any] | None = None
    if state.fn_call_result is not None:
        fc = state.fn_call_result
        fn_call_payload = {
            "tool_id": fc.tool_id,
            "rationale": fc.rationale,
            "missing_required_fields": fc.missing_required_fields,
            # Expose the LLM-proposed idempotency key for audit; never used for execution
            "llm_idempotency_key": fc.idempotency_key,
            "external": state.fn_call_external,
            "requires_confirmation": state.fn_call_requires_confirmation,
        }

    return {
        "request_id": state.request_id,
        "conv_id": state.conv_id,
        "verdict": state.verdict.value,
        "risk": state.risk,
        "intent": state.intent,
        "intent_detail": intent_payload,
        "fn_call_detail": fn_call_payload,
        "tool_id": state.tool_id,
        "tool_executed": state.tool_executed,
        "simulated": state.simulate,
        "result": state.tool_result,
        "output_verdict": state.output_verdict.value,
        "output_risk": state.output_risk,
        "message": state.final_response,
        "latency_ms": state.latency_ms,
        "findings_count": len(state.findings),
        "missing_required_fields": state.missing_required_fields,
        "pipeline_error": state.pipeline_error,
        # agent_steps reflects the actual ordered execution path captured by
        # the runner. With the audit-tail reorder (Response → Reporting →
        # Adaptive) `state.pipeline_stage` is no longer monotonic, so we
        # use `stages_executed` instead.
        "agent_steps": [
            {"stage": label, "name": f"stage{label}"}
            for label in state.stages_executed
        ],
    }
