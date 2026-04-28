"""ExplanationCard and shared agent finding types (Sentinel-X)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.sentinel import Finding, Verdict


class PolicyDecisionRecord(BaseModel):
    """OPA or policy sub-agent result."""

    package: str
    allowed: bool
    reasons: list[str] = Field(default_factory=list)


class AgentFindingRecord(BaseModel):
    """Entry on the shared blackboard."""

    agent: str
    claim: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    recommended_verdict: str | None = None
    recommended_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStepRecord(BaseModel):
    """Single step in agent trace (persisted + SSE)."""

    phase: str
    step: int
    thought: str = ""
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    observation: str = ""
    latency_ms: int = 0
    confidence: float | None = None


class ExplanationCard(BaseModel):
    """Mandatory structured explanation for a verdict (Sentinel-X)."""

    verdict: str  # allow Verdict or string for JSON
    confidence: float = 0.0
    headline: str = ""
    primary_reason: str = ""
    contributing_agents: list[str] = Field(default_factory=list)
    contributing_findings: list[Finding] = Field(default_factory=list)
    decisive_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    intent_classification: str = ""
    policy_decisions: list[PolicyDecisionRecord] = Field(default_factory=list)
    alternatives_considered: list[str] = Field(default_factory=list)
    user_facing_message: str = ""

    def to_verdict_enum(self) -> Verdict:
        v = (self.verdict or "ALLOW").upper()
        for e in Verdict:
            if e.value == v:
                return e
        return Verdict.ALLOW
