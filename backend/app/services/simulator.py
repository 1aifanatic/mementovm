from datetime import datetime

from sqlalchemy.orm import Session

from ..config import Settings
from ..schemas import EventCreate
from .runtime import RuntimeService


STEPS = [
    {
        "id": "lure_marketing_approval",
        "label": "Marketing approval lure",
        "description": "Related wording, wrong channel and entity.",
        "event": {
            "event_id": "evt-lure-marketing",
            "channel": "email",
            "event_type": "email.received",
            "occurred_at": "2026-07-16T09:05:00-05:00",
            "entity_keys": {"campaign_id": "campaign-91"},
            "payload": {"subject": "Approval required for the summer campaign"},
            "trust_class": "UNTRUSTED_TEXT",
        },
    },
    {
        "id": "lure_old_rejection",
        "label": "Stale legal rejection",
        "description": "Right contract, stale document version and wrong state.",
        "event": {
            "event_id": "evt-old-rejection",
            "channel": "legal",
            "event_type": "legal.response_received",
            "occurred_at": "2026-07-10T10:00:00-05:00",
            "entity_keys": {"contract_id": "contract-043", "document_version": "v6"},
            "payload": {"approval": {"status": "REJECTED"}},
        },
    },
    {
        "id": "legal_approval_current",
        "label": "Legal approves v7",
        "description": "First exact predicate becomes true; memory is primed.",
        "event": {
            "event_id": "evt-legal-v7-approved",
            "channel": "legal",
            "event_type": "legal.approval_changed",
            "occurred_at": "2026-07-16T09:20:00-05:00",
            "entity_keys": {"contract_id": "contract-043", "document_version": "v7"},
            "payload": {"approval": {"status": "APPROVED"}},
        },
    },
    {
        "id": "unrelated_finance",
        "label": "Other deal approved",
        "description": "Correct event type, hard deal-ID mismatch.",
        "event": {
            "event_id": "evt-finance-other-deal",
            "channel": "finance",
            "event_type": "finance.approval_changed",
            "occurred_at": "2026-07-16T09:26:00-05:00",
            "entity_keys": {"deal_id": "deal-999"},
            "payload": {"approval": {"status": "APPROVED"}},
        },
    },
    {
        "id": "focus_block_start",
        "label": "Focus block starts",
        "description": "Nonurgent interruptions are now deferred.",
        "event": {
            "event_id": "evt-focus-start",
            "channel": "calendar",
            "event_type": "calendar.focus_started",
            "occurred_at": "2026-07-16T09:30:00-05:00",
            "entity_keys": {"user_id": "demo-user"},
            "payload": {"start": "09:00", "end": "11:00"},
        },
    },
    {
        "id": "finance_approval_current",
        "label": "Finance approves deal",
        "description": "Compound cue completes, but focus policy defers interruption.",
        "event": {
            "event_id": "evt-finance-deal-043",
            "channel": "finance",
            "event_type": "finance.approval_changed",
            "occurred_at": "2026-07-16T10:08:00-05:00",
            "entity_keys": {"deal_id": "deal-043"},
            "payload": {"approval": {"status": "APPROVED"}},
        },
    },
    {
        "id": "focus_block_end",
        "label": "Focus block ends",
        "description": "The deferred draft now requests human approval.",
        "event": {
            "event_id": "evt-focus-end",
            "channel": "calendar",
            "event_type": "calendar.focus_ended",
            "occurred_at": "2026-07-16T11:00:00-05:00",
            "entity_keys": {"user_id": "demo-user"},
            "payload": {},
        },
    },
    {"id": "approve_action", "label": "Approve draft", "description": "One worker claims and creates the draft.", "approval": "APPROVE"},
    {
        "id": "duplicate_finance_event",
        "label": "Replay duplicate webhook",
        "description": "The event ID is deduplicated; no second draft is created.",
        "event": {
            "event_id": "evt-finance-deal-043",
            "channel": "finance",
            "event_type": "finance.approval_changed",
            "occurred_at": "2026-07-16T10:08:00-05:00",
            "entity_keys": {"deal_id": "deal-043"},
            "payload": {"approval": {"status": "APPROVED"}},
        },
    },
    {"id": "advance_absence_clock", "label": "Advance 48 hours", "description": "No legal response exists, so a Mark escalation draft is created.", "advance_time": "PT48H"},
]


class SimulatorService:
    def __init__(self, db: Session, settings: Settings):
        self.runtime = RuntimeService(db, settings)
        self.db = db

    def status(self) -> dict:
        intentions = self.runtime.list_intentions("demo-user")
        event_ids = {item.get("event_id") for item in self.runtime.timeline(200) if item.get("event_id")}
        completed = 0
        for step in STEPS:
            if step.get("event", {}).get("event_id") in event_ids:
                completed += 1
        return {"scenario_id": "contract-approval-official-demo", "steps": STEPS, "intentions": intentions, "completed_event_steps": completed}

    def run_step(self, step_id: str) -> dict:
        step = next((item for item in STEPS if item["id"] == step_id), None)
        if not step:
            raise KeyError("Simulator step not found")
        if "event" in step:
            event = step["event"]
            result = self.runtime.process_event(
                EventCreate(
                    user_id="demo-user",
                    source="simulator",
                    occurred_at=datetime.fromisoformat(event["occurred_at"]),
                    **{key: value for key, value in event.items() if key != "occurred_at"},
                )
            )
        elif step.get("approval"):
            approvals = self.runtime.pending_approvals()
            if not approvals:
                result = {"noop": True, "reason": "No approval is pending"}
            else:
                result = self.runtime.decide_approval(
                    approvals[0]["approval_id"], "APPROVE", "demo-operator"
                )
        else:
            result = self.runtime.advance_clock(step["advance_time"])
        return {"step": step, "result": result, "state": self.status()}

