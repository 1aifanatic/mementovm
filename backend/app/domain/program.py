from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


PRIMARY_MESSAGE = (
    "When legal approves the new DPA, prepare the redline for Dana. "
    "Do not send anything if the deal has already closed. "
    "If legal does not respond within two days, ask Mark. "
    "Avoid nonurgent alerts during my 9-to-11 focus block."
)
REVISION_MESSAGE = "Also wait for finance approval before preparing it."


def predicate(channel: str, field: str, value: Any, entities: dict[str, str]) -> dict:
    return {
        "predicate": {
            "source": "event",
            "channel": channel,
            "field": field,
            "operator": "changed_to",
            "value": value,
            "entity_constraints": entities,
        }
    }


def build_demo_program(
    *,
    intent_id: str,
    version: int,
    message_id: str,
    session_id: str,
    source_text: str,
    created_at: datetime | None = None,
    require_finance: bool = False,
    model: str = "deterministic-demo-compiler",
    request_id: str = "local-fallback",
) -> dict:
    created_at = created_at or datetime.now(timezone.utc)
    expected_by = created_at + timedelta(hours=48)
    triggers = [
        predicate(
            "legal",
            "payload.approval.status",
            "APPROVED",
            {"contract_id": "contract-043", "document_version": "v7"},
        )
    ]
    if require_finance:
        triggers.append(
            predicate(
                "finance",
                "payload.approval.status",
                "APPROVED",
                {"deal_id": "deal-043"},
            )
        )
    program = {
        "schema_version": "1.0.0",
        "intent_id": intent_id,
        "version": version,
        "user_id": "demo-user",
        "status": "DORMANT",
        "title": "Prepare Dana's DPA redline",
        "source": {
            "message_id": message_id,
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "original_quote": source_text,
            "parent_version": version - 1 if version > 1 else None,
            "source_spans": [
                {"field": "action", "quote": "prepare the redline for Dana"},
                {"field": "trigger", "quote": "When legal approves the new DPA"},
                {"field": "inhibitors", "quote": "if the deal has already closed"},
                {"field": "absence_rules", "quote": "If legal does not respond within two days"},
            ],
        },
        "action": {
            "action_id": "prepare-redline-draft",
            "tool_id": "email.create_draft",
            "arguments": {
                "recipient": "Dana",
                "subject": "DPA redline ready for review",
                "body_template": "Dana — the v7 DPA redline is ready for your review.",
                "contract_id": "contract-043",
            },
        },
        "trigger": {"all": triggers},
        "inhibitors": [
            {
                "predicate": {
                    "source": "state",
                    "channel": "contract",
                    "field": "contract.status",
                    "operator": "eq",
                    "value": "CLOSED",
                    "entity_constraints": {"contract_id": "contract-043"},
                }
            }
        ],
        "validity": [
            {
                "predicate": {
                    "source": "state",
                    "channel": "contract",
                    "field": "document.version",
                    "operator": "eq",
                    "value": "v7",
                    "entity_constraints": {"contract_id": "contract-043"},
                }
            }
        ],
        "absence_rules": [
            {
                "absence_rule_id": "legal-response-48h",
                "expected_event": {
                    "channel": "legal",
                    "event_type": "legal.response_received",
                    "entity_constraints": {"contract_id": "contract-043"},
                },
                "window": {"start": created_at.isoformat(), "expected_by": expected_by.isoformat()},
                "on_absence_action": {
                    "action_id": "ask-mark",
                    "tool_id": "notification.create_internal_draft",
                    "arguments": {
                        "recipient": "Mark",
                        "message": "Legal has not responded on contract-043 within 48 hours.",
                    },
                },
                "satisfied_by_event_id": None,
                "status": "WAITING",
            }
        ],
        "monitoring": {
            "channels": ["legal", "finance", "contract", "calendar"],
            "entity_keys": ["contract-043", "deal-043", "v7", "demo-user"],
            "next_check_at": expected_by.isoformat(),
            "priority": 0.86,
            "strategy": "EVENT_DRIVEN_WITH_DEADLINE_CHECK",
        },
        "interruption_policy": {
            "notification_urgency": "NORMAL",
            "respect_focus_time": True,
            "allowed_channels": ["in_app"],
        },
        "execution_policy": {
            "risk_tier": "EXTERNAL_WRITE",
            "approval": "REQUIRED",
            "max_attempts": 3,
            "timeout_seconds": 30,
            "idempotency_scope": "INTENT_VERSION_ACTION_OCCURRENCE",
        },
        "forgetting_policy": {
            "remove_from_hot_index_on": ["COMPLETED", "CANCELLED", "SUPERSEDED", "EXPIRED"],
            "raw_event_retention_days": 30,
            "source_message_retention_days": 90,
            "audit_retention_days": 365,
            "create_outcome_summary": True,
            "outcome_retention_days": 180,
            "retain_preferences": True,
            "allow_user_delete": True,
        },
        "confidence": {"overall": 0.94, "action": 0.98, "trigger": 0.93, "entities": 0.91},
        "assumptions": [],
        "unresolved_fields": [],
        "model_metadata": {
            "provider": "Qwen Cloud",
            "model": model,
            "prompt_version": "intent-compiler-v1",
            "request_id": request_id,
        },
    }
    return program


def revised_program(program: dict, *, message_id: str, session_id: str, source_text: str) -> dict:
    revised = deepcopy(program)
    revised["version"] += 1
    revised["status"] = "DORMANT"
    revised["source"] = {
        **revised["source"],
        "message_id": message_id,
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_quote": source_text,
        "parent_version": program["version"],
        "source_spans": [{"field": "trigger", "quote": source_text}],
    }
    finance = predicate(
        "finance", "payload.approval.status", "APPROVED", {"deal_id": "deal-043"}
    )
    if finance not in revised["trigger"]["all"]:
        revised["trigger"]["all"].append(finance)
    revised["monitoring"]["channels"] = sorted(set(revised["monitoring"]["channels"] + ["finance"]))
    return revised

