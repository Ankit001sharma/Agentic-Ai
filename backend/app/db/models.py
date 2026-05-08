"""SQLAlchemy ORM models for SentinelGuard."""

from __future__ import annotations

import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tier: Mapped[str] = mapped_column(String(32), default="free")
    region: Mapped[str] = mapped_column(String(32), default="global")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    attrs: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    request_count: Mapped[int] = mapped_column(Integer, default=0)


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    requested_model: Mapped[str] = mapped_column(String(128))
    selected_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    sensitivity: Mapped[str] = mapped_column(String(32), default="normal")

    prompt: Mapped[str] = mapped_column(Text)
    redacted_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    risk: Mapped[int] = mapped_column(Integer, default=0)
    output_risk: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(32), default="ALLOW")
    output_verdict: Mapped[str] = mapped_column(String(32), default="CLEAN")
    block_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Embedding of input prompt for vector recall scanner
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    findings: Mapped[list["FindingRow"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("requests.id"), index=True)
    side: Mapped[str] = mapped_column(String(16), default="input")  # input | output
    category: Mapped[str] = mapped_column(String(64), index=True)
    scanner: Mapped[str] = mapped_column(String(64))
    severity: Mapped[float] = mapped_column(Float)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    request: Mapped[Request] = relationship(back_populates="findings")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    rego: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggested_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    risk: Mapped[int] = mapped_column(Integer, default=0)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING / APPROVED / DENIED / TIMEOUT
    decision_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskGraphNode(Base):
    __tablename__ = "risk_graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_type: Mapped[str] = mapped_column(String(32), index=True)  # user | pattern | category | session
    key: Mapped[str] = mapped_column(String(255), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    attrs: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RiskGraphEdge(Base):
    __tablename__ = "risk_graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src: Mapped[int] = mapped_column(ForeignKey("risk_graph_nodes.id"), index=True)
    dst: Mapped[int] = mapped_column(ForeignKey("risk_graph_nodes.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class JailbreakEmbedding(Base):
    __tablename__ = "jailbreak_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="custom")
    category: Mapped[str] = mapped_column(String(64), default="JAILBREAK")
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class UserMemory(Base):
    """Long-term per-user memory promoted from STM on session end."""

    __tablename__ = "user_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    conv_id: Mapped[str] = mapped_column(String(64), index=True)
    last_intent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    tool_executions: Mapped[list] = mapped_column(JSON, default=list)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class AgentTrace(Base):
    """Persisted supervisor / specialist steps for Agent Trace replay."""

    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), ForeignKey("requests.id"), index=True, unique=True)
    agent_steps: Mapped[list] = mapped_column(JSON, default=list)
    assistant_steps: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_findings: Mapped[list] = mapped_column(JSON, default=list)
    agentic_trace_version: Mapped[str] = mapped_column(String(16), default="2")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
