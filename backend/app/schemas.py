from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    user_id: str = "demo-user"
    session_id: str = "session-a"
    client_request_id: str
    content: str = Field(min_length=1, max_length=10_000)


class RevisionCreate(BaseModel):
    session_id: str = "session-b"
    client_request_id: str
    content: str = Field(min_length=1, max_length=10_000)


class CancelCreate(BaseModel):
    reason: str
    client_request_id: str


class EventCreate(BaseModel):
    event_id: str
    user_id: str = "demo-user"
    source: str = "simulator"
    channel: str
    event_type: str
    occurred_at: datetime
    entity_keys: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    trust_class: Literal["TRUSTED_STRUCTURED", "UNTRUSTED_TEXT"] = "TRUSTED_STRUCTURED"


class ApprovalDecision(BaseModel):
    decision: Literal["APPROVE", "REJECT", "EDIT"]
    decided_by: str = "demo-operator"
    edited_arguments: dict[str, Any] | None = None


class ClockAdvance(BaseModel):
    duration: str = "PT48H"


class EvaluationRequest(BaseModel):
    dataset_version: str = "pm-mini-v1"
    baselines: list[str] = Field(
        default_factory=lambda: ["no-memory", "vector-memory", "todo-ledger", "mementovm"]
    )


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

