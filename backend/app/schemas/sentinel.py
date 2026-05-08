"""Sentinel-internal schemas: findings, scan state, verdict."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Intent Detection types (Stage 5) ─────────────────────────────────────────

class IntentType(str, Enum):
    SEND_EMAIL = "send_email"
    CREATE_TICKET = "create_ticket"
    SEARCH_DOCUMENTS = "search_documents"
    SCHEDULE_MEETING = "schedule_meeting"
    LOOKUP_USER = "lookup_user"
    SUMMARIZE = "summarize"
    CASUAL_CHAT = "casual_chat"
    NONE = "NONE"


class PersonEntity(BaseModel):
    name: str
    email: str | None = None
    resolved_from_memory: bool = False


class IntentEntities(BaseModel):
    people: list[PersonEntity] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    ids: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    raw_values: dict[str, str] = Field(default_factory=dict)


class IntentResult(BaseModel):
    """Structured output produced by the Mistral intent detector (Stage 5)."""

    intent: str = "NONE"
    entities: IntentEntities = Field(default_factory=IntentEntities)
    tool_id: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguous: bool = False
    clarification_needed: str | None = None
    memory_references_resolved: list[str] = Field(default_factory=list)


# ── Function Call types (Stage 8) ────────────────────────────────────────────

class FunctionCallResult(BaseModel):
    """Structured output produced by the Nemotron function-call generator (Stage 8)."""

    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    # LLM-proposed key stored for audit; pipeline always uses state.idempotency_key
    idempotency_key: str = ""
    rationale: str = ""
    missing_required_fields: list[str] = Field(default_factory=list)


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    MASK = "MASK"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


class OutputVerdict(str, Enum):
    CLEAN = "CLEAN"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


class Finding(BaseModel):
    """A single security finding produced by a scanner."""

    category: str
    severity: float = Field(ge=0.0, le=1.0)
    scanner: str
    evidence: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserContext(BaseModel):
    user_id: str = "anonymous"
    tier: str = "free"
    region: str = "global"
    historical_risk: float = 0.0
    session_id: str = "default"
    # Identity attestation:
    #   "human"  - normal end user
    #   "bot"    - automated agent (eligible for richer rate limits / monitoring)
    #   "service" - server-to-server / NHI workload identity
    auth_type: str = "human"
    # App-level RBAC role (e.g. "viewer", "analyst", "admin", "hr", "engineer").
    role: str = "viewer"
    # Optional resource the caller is asking about (e.g. "billing", "hr", "infra").
    resource: str | None = None
    # Agent / function-call context — used by Stage 8 (Nemotron) for text generation
    timezone: str = "UTC"
    language: str = "en"
    default_signature: str | None = None


class ScanState(BaseModel):
    """LangGraph shared state. Mutated through every agent node."""

    request_id: str
    user: UserContext = Field(default_factory=UserContext)
    sensitivity: str = "normal"
    requested_model: str = "gpt-4o-mini"
    # Routing hints inferred by the task classifier; consumed by ModelRoutingAgent.
    task: str = "chat"  # chat | coding | analysis | summarization | creative | classification
    complexity: str = "low"  # low | medium | high
    prompt: str = ""
    redacted_prompt: str | None = None
    redaction_map: dict[str, str] = Field(default_factory=dict)
    # Original user message before attachment text was merged in. Useful for
    # auditing what the user actually typed vs. what came from a file.
    original_prompt: str | None = None
    # Lightweight metadata about uploaded files (no raw bytes) — surfaced in
    # the sentinel response payload and the audit log.
    attachments: list[dict[str, Any]] = Field(default_factory=list)

    findings: list[Finding] = Field(default_factory=list)
    risk: int = 0
    risk_breakdown: dict[str, float] = Field(default_factory=dict)
    verdict: Verdict = Verdict.ALLOW
    block_reason: str | None = None

    opa_allowed: bool = True
    opa_reasons: list[str] = Field(default_factory=list)
    allowed_models: list[str] = Field(default_factory=list)
    selected_model: str | None = None
    # Ordered fallback chain produced by ModelRoutingAgent.select_model_smart
    # and consumed verbatim by LLMInvocationAgent (task + complexity + tier +
    # sensitivity + OPA-allowlist aware). Empty until the router has run.
    fallback_chain: list[str] = Field(default_factory=list)
    fallback_used: bool = False

    llm_response: str = ""
    output_findings: list[Finding] = Field(default_factory=list)
    output_risk: int = 0
    output_verdict: OutputVerdict = OutputVerdict.CLEAN
    final_response: str = ""

    # Agentic (Sentinel-X)
    intent: str | None = None
    intent_sub: str | None = None
    intent_confidence: float = 0.0
    agent_findings: list[dict[str, Any]] = Field(default_factory=list)
    agent_steps: list[dict[str, Any]] = Field(default_factory=list)
    assistant_steps: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    plan_hint: str | None = None
    self_corrections: int = 0
    rewrite_constraints: list[str] = Field(default_factory=list)
    output_reflection_verdict: str = ""
    human_escalation_brief: str | None = None
    explanation: dict[str, Any] | None = Field(
        default=None,
        description="Structured ExplanationCard payload for UI / audit.",
    )
    explanation_draft: dict[str, Any] | None = Field(
        default=None,
        description="Supervisor emit_explanation_card tool payload merged before final ExplanationCard.",
    )
    agentic_trace_version: str = "2"

    # Audit / telemetry
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    latency_ms: int = 0

    # ── Pipeline v2 fields ────────────────────────────────────────────────────
    # Conversation identifier; links to STM key stm:{user_id}:{conv_id}
    conv_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])

    # STM snapshot loaded at Stage 1; provides pronoun-resolution context at Stage 5
    stm_context: dict[str, Any] = Field(default_factory=dict)

    # Stage 5: full typed IntentResult from Mistral
    intent_result: IntentResult | None = None
    # Flat entity list kept for backward-compat with STM and existing code
    intent_entities: list[str] = Field(default_factory=list)
    intent_ambiguous: bool = False
    intent_clarification: str | None = None
    memory_references_resolved: list[str] = Field(default_factory=list)

    # Stage 6: resolved tool
    tool_id: str | None = None
    tool_schema: dict[str, Any] | None = None
    tool_definition: dict[str, Any] | None = None  # full YAML entry

    # Stage 8: full typed FunctionCallResult from Nemotron
    fn_call_result: FunctionCallResult | None = None
    # Convenience aliases populated from fn_call_result
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_args_rationale: str | None = None
    # Fields the LLM could not populate from available context
    missing_required_fields: list[str] = Field(default_factory=list)
    # True when arguments contain external:true or requires_confirmation:true
    fn_call_external: bool = False
    fn_call_requires_confirmation: bool = False

    # Stage 11: execution result
    tool_result: dict[str, Any] | None = None
    tool_executed: bool = False

    # Idempotency + dry-run
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex)
    simulate: bool = False

    # Stage 7: OPA policy denial (distinct from security BLOCK — returns 200 not 403)
    policy_denied: bool = False

    # Stage 10: high-impact gate
    high_impact: bool = False
    human_review_required: bool = False
    human_review_decision: str | None = None  # "approved" | "rejected" | "timeout"

    # Pipeline progress tracker (1-14). Reflects the most recent stage that
    # ran; with the reordered runner this is NOT monotonic, so analytics
    # should prefer `stages_executed` for ordered traces.
    pipeline_stage: int = 0

    # Ordered list of stage labels actually executed in this request, e.g.
    # ["01","02","03","04","05","06","07","08","09","10","11","11b","14","12","13"]
    # Populated by the PipelineRunner after each successful stage.
    stages_executed: list[str] = Field(default_factory=list)

    # Structured error envelope: {code, message, retryable, user_facing}
    pipeline_error: dict[str, Any] | None = None

    class Config:
        use_enum_values = False
