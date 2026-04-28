"""Sentinel-internal schemas: findings, scan state, verdict."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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

    class Config:
        use_enum_values = False
