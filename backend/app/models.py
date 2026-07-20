from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Demo Operator")
    timezone: Mapped[str] = mapped_column(String(80), default="America/Chicago")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(20), default="user")
    content: Mapped[str] = mapped_column(Text)
    client_request_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Intention(Base):
    __tablename__ = "intentions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    active_version: Mapped[int] = mapped_column(Integer, default=1)
    current_status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class IntentionVersion(Base):
    __tablename__ = "intention_versions"
    __table_args__ = (UniqueConstraint("intention_id", "version"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    intention_id: Mapped[str] = mapped_column(ForeignKey("intentions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    program: Mapped[dict] = mapped_column(JSON)
    source_message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    parent_version_id: Mapped[str | None] = mapped_column(ForeignKey("intention_versions.id"))
    compiler_model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CueIndex(Base):
    __tablename__ = "cue_indexes"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(ForeignKey("intention_versions.id"), index=True)
    channel: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_key: Mapped[str] = mapped_column(String(200), index=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(80))
    channel: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    entity_keys: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    trust_class: Mapped[str] = mapped_column(String(40), default="TRUSTED_STRUCTURED")
    content_hash: Mapped[str] = mapped_column(String(64))


class EventEvaluation(Base):
    __tablename__ = "event_evaluations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    version_id: Mapped[str | None] = mapped_column(ForeignKey("intention_versions.id"), index=True)
    candidate_rank: Mapped[int] = mapped_column(Integer, default=0)
    predicate_results: Mapped[dict] = mapped_column(JSON, default=dict)
    match_confidence: Mapped[float] = mapped_column(Float, default=0)
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    model_request_id: Mapped[str | None] = mapped_column(String(120))
    context_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class MonitoringJob(Base):
    __tablename__ = "monitoring_jobs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    version_id: Mapped[str | None] = mapped_column(ForeignKey("intention_versions.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(30))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(ForeignKey("intention_versions.id"), index=True)
    action_id: Mapped[str] = mapped_column(String(100))
    tool_id: Mapped[str] = mapped_column(String(120))
    arguments: Mapped[dict] = mapped_column(JSON)
    risk_tier: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    result: Mapped[dict | None] = mapped_column(JSON)
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    action_id: Mapped[str] = mapped_column(ForeignKey("actions.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(30))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(120))
    action_hash: Mapped[str] = mapped_column(String(64))


class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (UniqueConstraint("user_id", "key", "version"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(80), index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class StateTransition(Base):
    __tablename__ = "state_transitions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(ForeignKey("intention_versions.id"), index=True)
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    cause_type: Mapped[str] = mapped_column(String(40))
    cause_id: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=uid)
    dataset_version: Mapped[str] = mapped_column(String(80))
    baseline: Mapped[str] = mapped_column(String(80))
    git_commit: Mapped[str] = mapped_column(String(80), default="working-tree")
    model_config: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
