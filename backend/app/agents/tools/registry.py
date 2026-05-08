"""Tool registry: dispatch and OpenAI tool schemas for vLLM (Nemotron supervisor)."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from app.schemas.sentinel import ScanState
from app.agents.tools.base import ToolResult
from app.agents.tools import security

ToolHandler = Callable[..., Awaitable[ToolResult]]


def _func_schema(name: str, desc: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


OPENAI_SUPERVISOR_TOOLS: list[dict[str, Any]] = [
    _func_schema(
        "delegate_to_intent",
        "Classify user intent (data extraction, jailbreak, code, etc.)",
        {},
    ),
    _func_schema(
        "delegate_to_threat",
        "Run threat investigation scanners on the prompt",
        {},
    ),
    _func_schema("delegate_to_policy", "Apply OPA + contextual policy", {}),
    _func_schema("delegate_to_multimodal", "If attachments, scan image/doc/url/metadata", {}),
    _func_schema("delegate_to_model_router", "Select upstream model and fallback chain", {}),
    _func_schema("delegate_to_human_escalation", "Decide if human review needed; emit brief", {}),
    _func_schema(
        "query_miniorange_docs",
        "Search miniOrange plugin documentation (OAuth, SAML, SSO, LDAP, 2FA, WordPress, Joomla, Drupal, etc.) for integration guides, setup instructions, and troubleshooting. Returns top matching docs with optional AI synthesis.",
        {
            "query": {"type": "string", "description": "Search query, e.g. 'Joomla SAML SSO setup'"},
            "top_k": {"type": "integer", "description": "Max docs to return (default 3)"},
        },
        required=["query"],
    ),
    _func_schema(
        "list_miniorange_plugins",
        "List all miniOrange plugin/service titles available in the documentation index.",
        {},
    ),
    _func_schema(
        "get_miniorange_plugin",
        "Get auth type, required credentials, setup steps, and env template for a specific miniOrange plugin/service.",
        {
            "service": {"type": "string", "description": "Service name, e.g. 'OAuth', 'Joomla SAML SSO'"},
        },
        required=["service"],
    ),
    _func_schema(
        "emit_explanation_card",
        "Terminal: emit final verdict, confidence, headline, reasons",
        {
            "verdict": {"type": "string", "enum": ["ALLOW", "MASK", "ESCALATE", "BLOCK"]},
            "confidence": {"type": "number"},
            "headline": {"type": "string"},
            "user_facing_message": {"type": "string"},
            "primary_reason": {"type": "string"},
        },
        required=["verdict", "confidence", "headline", "user_facing_message", "primary_reason"],
    ),
    _func_schema(
        "run_full_input_scan",
        "Run the full legacy input scanner battery (11 scanners + borderline judge). Same as AGENT_PRESCAN=full_threat.",
        {},
    ),
    _func_schema("scan_pii", "Run PII scanner on text", {"text": {"type": "string"}}, ["text"]),
    _func_schema("scan_secrets", "Run secrets scanner", {"text": {"type": "string"}}, ["text"]),
    _func_schema(
        "scan_injection",
        "Regex + embedding jailbreak/injection scan",
        {"text": {"type": "string"}},
        ["text"],
    ),
    _func_schema("scan_toxicity", "Toxicity classifier", {"text": {"type": "string"}}, ["text"]),
    _func_schema("scan_malware", "Malware intent scan", {"text": {"type": "string"}}, ["text"]),
    _func_schema("check_rbac", "RBAC / role violation scan", {"text": {"type": "string"}}, ["text"]),
    _func_schema("scan_code_ip", "Proprietary code / IP patterns", {"text": {"type": "string"}}, ["text"]),
    _func_schema("scan_internal", "Unverified internal-information requests", {"text": {"type": "string"}}, ["text"]),
    _func_schema("scan_nhi", "Non-human identity workload checks", {"text": {"type": "string"}}, ["text"]),
    _func_schema(
        "recall_similar",
        "Vector recall vs past BLOCK/ESCALATE requests (repeat attack)",
        {"text": {"type": "string"}},
        ["text"],
    ),
    _func_schema(
        "memory_recall_similar",
        "Episodic memory: top similar past incidents with similarity scores (pgvector)",
        {
            "text": {"type": "string", "description": "Prompt to embed; defaults to current user prompt"},
            "k": {"type": "integer", "description": "Number of incidents (default 5)"},
        },
    ),
    _func_schema("opa_evaluate", "Evaluate base OPA sentinel policy for current state", {}),
]


def supervisor_tool_names_hint() -> str:
    names: list[str] = []
    for spec in OPENAI_SUPERVISOR_TOOLS:
        fn = spec.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            names.append(str(fn["name"]))
    return ", ".join(names)


async def dispatch(
    name: str,
    args: dict[str, Any],
    state: ScanState,
) -> ToolResult:
    t0 = time.perf_counter()
    text = args.get("text") or state.prompt

    if name == "run_full_input_scan":
        return await security.tool_run_full_input_scan(state)
    if name == "scan_pii":
        return await security.tool_scan_pii(text, state)
    if name == "scan_secrets":
        return await security.tool_scan_secrets(text, state)
    if name == "scan_injection":
        return await security.tool_scan_injection(text, state)
    if name == "scan_toxicity":
        return await security.tool_scan_toxicity(text, state)
    if name == "scan_malware":
        return await security.tool_scan_malware(text, state)
    if name == "check_rbac":
        return await security.tool_check_rbac(text, state)
    if name == "scan_code_ip":
        return await security.tool_scan_code_ip(text, state)
    if name == "scan_internal":
        return await security.tool_scan_internal(text, state)
    if name == "scan_nhi":
        return await security.tool_scan_nhi(text, state)
    if name == "recall_similar" or name == "vector_recall":
        return await security.tool_recall_vector(text, state)
    if name == "memory_recall_similar":
        k = int(args.get("k") or 5)
        return await security.tool_memory_recall_similar(text, state, k=k)
    if name == "opa_evaluate":
        return await security.tool_opa_base(state)

    if name == "query_miniorange_docs":
        from app.agents.tools.miniorange import tool_query_miniorange_docs
        return await tool_query_miniorange_docs(args.get("query") or state.prompt, state)

    if name == "list_miniorange_plugins":
        from app.agents.tools.miniorange import tool_list_miniorange_plugins
        return await tool_list_miniorange_plugins(state)

    if name == "get_miniorange_plugin":
        from app.agents.tools.miniorange import tool_get_miniorange_plugin
        return await tool_get_miniorange_plugin(args.get("service", ""), state)

    if name == "emit_explanation_card":
        state.explanation_draft = dict(args)
        return ToolResult(
            ok=True,
            name=name,
            summary="explanation_card_emitted",
            data=args,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    hint = supervisor_tool_names_hint()
    return ToolResult(
        ok=False,
        name=name,
        summary=f"unknown_tool; use one of: {hint}"[:8000],
        error="unknown",
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


def get_supervisor_openai_tools() -> list[dict[str, Any]]:
    return OPENAI_SUPERVISOR_TOOLS
