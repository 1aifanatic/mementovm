from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..config import Settings
from ..domain.program import PRIMARY_MESSAGE, REVISION_MESSAGE, build_demo_program, revised_program
from ..models import (
    Action,
    Approval,
    CueIndex,
    Event,
    EventEvaluation,
    Intention,
    IntentionVersion,
    Message,
    MonitoringJob,
    Preference,
    SessionRecord,
    StateTransition,
    User,
    now_utc,
    uid,
)
from ..schemas import EventCreate, MessageCreate, RevisionCreate
from .validator import validate_program


ACTIVE_STATES = {"DORMANT", "PRIMED", "DUE", "AWAITING_APPROVAL", "EXECUTING"}
TERMINAL_STATES = {"COMPLETED", "CANCELLED", "SUPERSEDED", "EXPIRED", "MISSED", "FAILED"}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class RuntimeService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def ensure_user(self, user_id: str = "demo-user") -> User:
        user = self.db.get(User, user_id)
        if user is None:
            user = User(id=user_id, display_name="Avery Chen", timezone="America/Chicago")
            self.db.add(user)
            self.db.flush()
        return user

    def ensure_session(self, session_id: str, user_id: str) -> SessionRecord:
        session = self.db.get(SessionRecord, session_id)
        if session is None:
            session = SessionRecord(id=session_id, user_id=user_id)
            self.db.add(session)
            self.db.flush()
        return session

    def store_message(self, request: MessageCreate | RevisionCreate, user_id: str) -> tuple[Message, bool]:
        existing = self.db.scalar(
            select(Message).where(Message.client_request_id == request.client_request_id)
        )
        if existing:
            return existing, True
        self.ensure_user(user_id)
        self.ensure_session(request.session_id, user_id)
        message = Message(
            id=uid(),
            user_id=user_id,
            session_id=request.session_id,
            content=request.content,
            client_request_id=request.client_request_id,
            correlation_id=request.client_request_id,
        )
        self.db.add(message)
        self.db.flush()
        return message, False

    def _transition(
        self,
        version: IntentionVersion,
        to_state: str,
        *,
        cause_type: str,
        cause_id: str,
        reason: str,
        details: dict | None = None,
    ) -> None:
        old = version.status
        version.status = to_state
        if to_state in TERMINAL_STATES:
            version.terminal_at = now_utc()
            self.db.execute(
                update(CueIndex).where(CueIndex.version_id == version.id).values(active=False)
            )
            self.db.execute(
                update(MonitoringJob)
                .where(MonitoringJob.version_id == version.id, MonitoringJob.status == "PENDING")
                .values(status="CANCELLED")
            )
        intention = self.db.get(Intention, version.intention_id)
        if intention and intention.active_version == version.version:
            intention.current_status = to_state
            intention.updated_at = now_utc()
        self.db.add(
            StateTransition(
                version_id=version.id,
                from_state=old,
                to_state=to_state,
                cause_type=cause_type,
                cause_id=cause_id,
                reason=reason,
                details=details or {},
            )
        )

    def _index_version(self, version: IntentionVersion) -> None:
        program = version.program
        channels = program.get("monitoring", {}).get("channels", [])
        entity_keys = program.get("monitoring", {}).get("entity_keys", []) or ["*"]
        event_types: dict[str, str] = {
            "legal": "legal.approval_changed",
            "finance": "finance.approval_changed",
            "contract": "contract.status_changed",
            "calendar": "calendar.focus_changed",
        }
        for channel in channels:
            for entity in entity_keys:
                self.db.add(
                    CueIndex(
                        version_id=version.id,
                        channel=channel,
                        event_type=event_types.get(channel, "*"),
                        entity_key=entity,
                        active=True,
                    )
                )

    def activate_program(self, message: Message, program: dict) -> Intention:
        intention = Intention(
            id=program["intent_id"],
            user_id=message.user_id,
            title=program["title"],
            active_version=program["version"],
            current_status="CAPTURED",
        )
        version = IntentionVersion(
            id=uid(),
            intention_id=intention.id,
            version=program["version"],
            status="CAPTURED",
            program=program,
            source_message_id=message.id,
            compiler_model=program["model_metadata"]["model"],
            prompt_version=program["model_metadata"]["prompt_version"],
            confidence=program["confidence"]["overall"],
        )
        self.db.add_all([intention, version])
        self.db.flush()
        validation_errors = validate_program(program)
        if validation_errors:
            self._transition(
                version,
                "QUARANTINED",
                cause_type="validator",
                cause_id=message.id,
                reason="Program is quarantined because validation failed.",
                details={"errors": validation_errors},
            )
            self.db.commit()
            return intention
        self._transition(
            version,
            "VALIDATED",
            cause_type="compiler",
            cause_id=message.id,
            reason="Schema and deterministic safety policy passed.",
            details={
                "repair_attempted": bool(program["model_metadata"].get("repair_attempted")),
                "unresolved_fields": program.get("unresolved_fields", []),
            },
        )
        self._transition(
            version,
            "DORMANT",
            cause_type="activation",
            cause_id=message.id,
            reason="Program activated and indexed for relevant future cues.",
            details={"channels": program["monitoring"]["channels"]},
        )
        self._index_version(version)
        deadline = datetime.fromisoformat(program["absence_rules"][0]["window"]["expected_by"])
        self.db.add(
            MonitoringJob(
                version_id=version.id,
                job_type="ABSENCE",
                run_at=deadline,
                payload={"absence_rule_id": "legal-response-48h"},
            )
        )
        self._upsert_focus_preference(message.user_id, message.id, active=False)
        self.db.commit()
        return intention

    def create_intention(self, request: MessageCreate, compiled: dict | None = None) -> dict:
        message, duplicate = self.store_message(request, request.user_id)
        if duplicate:
            version = self.db.scalar(
                select(IntentionVersion).where(IntentionVersion.source_message_id == message.id)
            )
            if version:
                return self._message_response(message, version, idempotent=True)
        intent_id = uid()
        program = compiled or build_demo_program(
            intent_id=intent_id,
            version=1,
            message_id=message.id,
            session_id=message.session_id,
            source_text=message.content,
            model="deterministic-demo-compiler",
            request_id="fallback-no-cloud-call",
        )
        program["intent_id"] = intent_id
        program["user_id"] = request.user_id
        program["source"]["message_id"] = message.id
        program["source"]["session_id"] = message.session_id
        program["source"]["original_quote"] = message.content
        intention = self.activate_program(message, program)
        version = self._active_version(intention)
        return self._message_response(message, version)

    def _message_response(
        self, message: Message, version: IntentionVersion, *, idempotent: bool = False
    ) -> dict:
        return {
            "message_id": message.id,
            "classification": "NEW_INTENTION",
            "intention": {
                "intent_id": version.intention_id,
                "version": version.version,
                "status": version.status,
                "title": version.program["title"],
            },
            "requires_confirmation": version.status == "QUARANTINED",
            "explanation": (
                "Waiting for the required approvals while the contract remains open. "
                "External communication stays behind a human approval gate."
            ),
            "idempotent_replay": idempotent,
            "compiler": version.program["model_metadata"],
        }

    def revise_intention(self, intent_id: str, request: RevisionCreate) -> dict:
        intention = self.db.get(Intention, intent_id)
        if not intention:
            raise KeyError("Intention not found")
        message, duplicate = self.store_message(request, intention.user_id)
        if duplicate:
            existing = self.db.scalar(
                select(IntentionVersion).where(IntentionVersion.source_message_id == message.id)
            )
            if existing:
                return self.serialize_intention(intention)
        old = self._active_version(intention)
        if old.status in TERMINAL_STATES:
            raise ValueError("Terminal intentions cannot be revised")
        program = revised_program(
            old.program,
            message_id=message.id,
            session_id=request.session_id,
            source_text=request.content,
        )
        new = IntentionVersion(
            id=uid(),
            intention_id=intention.id,
            version=old.version + 1,
            status="CAPTURED",
            program=program,
            source_message_id=message.id,
            parent_version_id=old.id,
            compiler_model=program["model_metadata"]["model"],
            prompt_version="revision-v1",
            confidence=0.96,
        )
        self.db.add(new)
        self.db.flush()
        self._transition(
            old,
            "SUPERSEDED",
            cause_type="revision",
            cause_id=message.id,
            reason="A later user instruction added finance approval.",
        )
        self._transition(
            new,
            "VALIDATED",
            cause_type="revision",
            cause_id=message.id,
            reason="Version patch validated as a complete immutable snapshot.",
            details={"changed_fields": ["trigger.all", "monitoring.channels"]},
        )
        intention.active_version = new.version
        self._transition(
            new,
            "DORMANT",
            cause_type="activation",
            cause_id=message.id,
            reason="Version 2 activated; version 1 removed from the hot index.",
        )
        self._index_version(new)
        self.db.commit()
        return self.serialize_intention(intention)

    def cancel_intention(self, intent_id: str, reason: str, client_request_id: str) -> dict:
        intention = self.db.get(Intention, intent_id)
        if not intention:
            raise KeyError("Intention not found")
        version = self._active_version(intention)
        if version.status not in TERMINAL_STATES:
            self._transition(
                version,
                "CANCELLED",
                cause_type="message",
                cause_id=client_request_id,
                reason=reason,
            )
            self.db.commit()
        return self.serialize_intention(intention)

    def delete_intention(self, intent_id: str) -> None:
        intention = self.db.get(Intention, intent_id)
        if not intention:
            raise KeyError("Intention not found")
        version_ids = list(
            self.db.scalars(
                select(IntentionVersion.id).where(IntentionVersion.intention_id == intent_id)
            )
        )
        action_ids = list(self.db.scalars(select(Action.id).where(Action.version_id.in_(version_ids))))
        if action_ids:
            self.db.execute(delete(Approval).where(Approval.action_id.in_(action_ids)))
        self.db.execute(delete(Action).where(Action.version_id.in_(version_ids)))
        self.db.execute(delete(EventEvaluation).where(EventEvaluation.version_id.in_(version_ids)))
        self.db.execute(delete(StateTransition).where(StateTransition.version_id.in_(version_ids)))
        self.db.execute(delete(CueIndex).where(CueIndex.version_id.in_(version_ids)))
        self.db.execute(delete(MonitoringJob).where(MonitoringJob.version_id.in_(version_ids)))
        self.db.execute(delete(IntentionVersion).where(IntentionVersion.intention_id == intent_id))
        self.db.delete(intention)
        self.db.commit()

    def _active_version(self, intention: Intention) -> IntentionVersion:
        version = self.db.scalar(
            select(IntentionVersion).where(
                IntentionVersion.intention_id == intention.id,
                IntentionVersion.version == intention.active_version,
            )
        )
        if version is None:
            raise RuntimeError("Active version is missing")
        return version

    def _current_intention(self, user_id: str = "demo-user") -> Intention | None:
        return self.db.scalar(
            select(Intention)
            .where(Intention.user_id == user_id)
            .order_by(Intention.updated_at.desc())
        )

    def _upsert_focus_preference(self, user_id: str, source_id: str | None, *, active: bool) -> None:
        old = self.db.scalar(
            select(Preference)
            .where(Preference.user_id == user_id, Preference.key == "focus_time", Preference.active)
            .order_by(Preference.version.desc())
        )
        version = 1
        if old:
            old.active = False
            version = old.version + 1
        self.db.add(
            Preference(
                user_id=user_id,
                key="focus_time",
                value={"start": "09:00", "end": "11:00", "timezone": "America/Chicago", "active": active},
                version=version,
                source_message_id=source_id if source_id and self.db.get(Message, source_id) else None,
                active=True,
            )
        )

    def focus_active(self, user_id: str) -> bool:
        pref = self.db.scalar(
            select(Preference)
            .where(Preference.user_id == user_id, Preference.key == "focus_time", Preference.active)
            .order_by(Preference.version.desc())
        )
        return bool(pref and pref.value.get("active"))

    def _record_evaluation(
        self,
        event: Event,
        version: IntentionVersion | None,
        *,
        decision: str,
        reason: str,
        confidence: float,
        results: dict | None = None,
        candidate_rank: int = 0,
    ) -> None:
        self.db.add(
            EventEvaluation(
                event_id=event.id,
                version_id=version.id if version else None,
                candidate_rank=candidate_rank,
                predicate_results=results or {},
                match_confidence=confidence,
                decision=decision,
                reason=reason,
                context_tokens=0,
            )
        )

    def process_event(self, request: EventCreate) -> dict:
        existing = self.db.get(Event, request.event_id)
        if existing:
            return {
                "event_id": existing.id,
                "deduplicated": True,
                "candidate_count": 0,
                "evaluations": [],
                "transitions": [],
                "actions_created": 0,
            }
        event = Event(
            id=request.event_id,
            user_id=request.user_id,
            source=request.source,
            channel=request.channel,
            event_type=request.event_type,
            occurred_at=request.occurred_at,
            entity_keys=request.entity_keys,
            payload=request.payload,
            trust_class=request.trust_class,
            content_hash=digest(request.model_dump(mode="json")),
        )
        self.db.add(event)
        self.db.flush()
        intention = self._current_intention(request.user_id)
        version = self._active_version(intention) if intention else None
        before = version.status if version else None

        if request.channel == "calendar" and request.event_type == "calendar.focus_started":
            self._upsert_focus_preference(request.user_id, None, active=True)
            self._record_evaluation(
                event,
                version,
                decision="MATCH",
                reason="Focus block is active; nonurgent notifications will be deferred.",
                confidence=1.0,
                results={"preference": "focus_time", "active": True},
                candidate_rank=1,
            )
        elif request.channel == "calendar" and request.event_type == "calendar.focus_ended":
            self._upsert_focus_preference(request.user_id, None, active=False)
            self._record_evaluation(
                event,
                version,
                decision="MATCH",
                reason="Focus block ended; deferred actions may request approval.",
                confidence=1.0,
                results={"preference": "focus_time", "active": False},
                candidate_rank=1,
            )
            if version and version.status == "DUE":
                action = self.db.scalar(
                    select(Action).where(Action.version_id == version.id, Action.status == "DEFERRED")
                )
                if action:
                    self._request_approval(version, action, cause_id=event.id)
        elif not version or version.status not in ACTIVE_STATES:
            self._record_evaluation(
                event,
                version,
                decision="REJECT",
                reason="No active Intention Program is eligible for retrieval.",
                confidence=0.0,
            )
        else:
            match, reason, confidence, results = self._match_event(event, version)
            self._record_evaluation(
                event,
                version,
                decision="MATCH" if match else "REJECT",
                reason=reason,
                confidence=confidence,
                results=results,
                candidate_rank=1 if match else 0,
            )
            if match:
                self._apply_match(event, version)
        self.db.commit()
        self.db.refresh(event)
        after = self._active_version(intention).status if intention else None
        action_count = self.db.scalar(
            select(func.count(Action.id)).where(Action.created_at >= event.received_at)
        )
        evaluation = self.db.scalar(
            select(EventEvaluation)
            .where(EventEvaluation.event_id == event.id)
            .order_by(EventEvaluation.created_at.desc())
        )
        return {
            "event_id": event.id,
            "deduplicated": False,
            "candidate_count": 1 if evaluation and evaluation.candidate_rank else 0,
            "evaluations": [self.serialize_evaluation(evaluation)] if evaluation else [],
            "transitions": ([{"from": before, "to": after}] if before != after else []),
            "actions_created": action_count or 0,
        }

    def _match_event(
        self, event: Event, version: IntentionVersion
    ) -> tuple[bool, str, float, dict]:
        entities = event.entity_keys or {}
        status = (event.payload or {}).get("approval", {}).get("status")
        if event.channel == "email":
            return False, "Channel and entity indexes rejected a marketing approval lure.", 0.0, {
                "channel_match": False,
                "semantic_model_called": False,
            }
        if event.channel == "legal":
            if entities.get("contract_id") != "contract-043":
                return False, "Hard contract identifier mismatch.", 0.0, {"contract_id": False}
            if entities.get("document_version") != "v7":
                return False, "Stale document version; expected v7.", 0.0, {
                    "contract_id": True,
                    "document_version": False,
                }
            if status != "APPROVED":
                return False, "Legal response did not change approval to APPROVED.", 0.0, {
                    "approval_status": False
                }
            return True, "Exact legal approval cue matched contract-043 and document v7.", 1.0, {
                "contract_id": True,
                "document_version": True,
                "approval_status": True,
                "semantic_model_called": False,
            }
        if event.channel == "finance":
            if entities.get("deal_id") != "deal-043":
                return False, "Hard deal identifier mismatch; finance approval belongs to another deal.", 0.0, {
                    "deal_id": False
                }
            if status != "APPROVED":
                return False, "Finance approval predicate is false.", 0.0, {"approval_status": False}
            return True, "Exact finance approval cue matched deal-043.", 1.0, {
                "deal_id": True,
                "approval_status": True,
                "semantic_model_called": False,
            }
        if event.channel == "contract" and entities.get("contract_id") == "contract-043":
            if (event.payload or {}).get("status") == "CLOSED":
                return False, "Contract-closed inhibitor is true; action is blocked.", 0.0, {
                    "inhibitor": True
                }
        return False, "No deterministic predicate matched the normalized event.", 0.0, {
            "semantic_model_called": False
        }

    def _has_match(self, channel: str, event_type: str) -> bool:
        events = self.db.scalars(
            select(Event).where(Event.channel == channel, Event.event_type == event_type)
        )
        for event in events:
            if channel == "legal":
                if (
                    event.entity_keys.get("contract_id") == "contract-043"
                    and event.entity_keys.get("document_version") == "v7"
                    and event.payload.get("approval", {}).get("status") == "APPROVED"
                ):
                    return True
            if channel == "finance":
                if (
                    event.entity_keys.get("deal_id") == "deal-043"
                    and event.payload.get("approval", {}).get("status") == "APPROVED"
                ):
                    return True
        return False

    def _apply_match(self, event: Event, version: IntentionVersion) -> None:
        requires_finance = len(version.program.get("trigger", {}).get("all", [])) > 1
        legal = self._has_match("legal", "legal.approval_changed")
        finance = self._has_match("finance", "finance.approval_changed")
        ready = legal and (finance or not requires_finance)
        if ready:
            self._transition(
                version,
                "DUE",
                cause_type="event",
                cause_id=event.id,
                reason="Every compound trigger is true; validity holds and inhibitors are false.",
                details={"legal_approved": legal, "finance_approved": finance},
            )
            action = self._ensure_action(version)
            if self.focus_active(event.user_id):
                action.status = "DEFERRED"
                self.db.add(
                    StateTransition(
                        version_id=version.id,
                        from_state="DUE",
                        to_state="DUE",
                        cause_type="preference",
                        cause_id="focus_time",
                        reason="Nonurgent approval notification deferred until the 9–11 focus block ends.",
                        details={"preference": "focus_time", "deferred": True},
                    )
                )
            else:
                self._request_approval(version, action, cause_id=event.id)
        elif version.status != "PRIMED":
            self._transition(
                version,
                "PRIMED",
                cause_type="event",
                cause_id=event.id,
                reason="One compound trigger matched; the remaining approval is still pending.",
                details={"legal_approved": legal, "finance_approved": finance},
            )

    def _ensure_action(self, version: IntentionVersion) -> Action:
        key = digest(
            f"{version.program['user_id']}:{version.intention_id}:{version.version}:"
            f"{version.program['action']['action_id']}:once"
        )
        action = self.db.scalar(select(Action).where(Action.idempotency_key == key))
        if action:
            return action
        spec = version.program["action"]
        action = Action(
            version_id=version.id,
            action_id=spec["action_id"],
            tool_id=spec["tool_id"],
            arguments=spec["arguments"],
            risk_tier=version.program["execution_policy"]["risk_tier"],
            status="DUE",
            idempotency_key=key,
        )
        self.db.add(action)
        self.db.flush()
        return action

    def _request_approval(self, version: IntentionVersion, action: Action, cause_id: str) -> Approval:
        existing = self.db.scalar(
            select(Approval).where(Approval.action_id == action.id, Approval.decision.is_(None))
        )
        if existing:
            return existing
        action.status = "AWAITING_APPROVAL"
        approval = Approval(
            action_id=action.id,
            action_hash=digest(action.arguments),
            expires_at=now_utc() + timedelta(minutes=self.settings.approval_ttl_minutes),
        )
        self.db.add(approval)
        self._transition(
            version,
            "AWAITING_APPROVAL",
            cause_type="policy",
            cause_id=cause_id,
            reason="External write is bound to this action hash and requires human approval.",
            details={"action_hash": approval.action_hash, "risk_tier": action.risk_tier},
        )
        return approval

    def decide_approval(
        self,
        approval_id: str,
        decision: str,
        decided_by: str,
        edited_arguments: dict | None = None,
    ) -> dict:
        approval = self.db.get(Approval, approval_id)
        if not approval:
            raise KeyError("Approval not found")
        action = self.db.get(Action, approval.action_id)
        version = self.db.get(IntentionVersion, action.version_id) if action else None
        if not action or not version:
            raise RuntimeError("Approval target is missing")
        if approval.decision:
            return self.serialize_action(action) | {"idempotent_replay": True}
        expires_at = approval.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now_utc():
            approval.decision = "EXPIRED"
            approval.decided_at = now_utc()
            action.status = "AWAITING_APPROVAL"
            self.db.commit()
            raise ValueError("Approval expired; request a new approval before execution")
        if digest(action.arguments) != approval.action_hash:
            raise ValueError("Action changed after approval was requested")
        approval.decision = decision
        approval.decided_at = now_utc()
        approval.decided_by = decided_by
        if decision == "EDIT":
            if not edited_arguments:
                raise ValueError("Edited arguments are required")
            action.arguments = edited_arguments
            action.status = "AWAITING_APPROVAL"
            self.db.add(
                Approval(
                    action_id=action.id,
                    action_hash=digest(action.arguments),
                    expires_at=now_utc() + timedelta(minutes=self.settings.approval_ttl_minutes),
                )
            )
            self.db.commit()
            return self.serialize_action(action)
        if decision == "REJECT":
            action.status = "REJECTED"
            self._transition(
                version,
                "DORMANT",
                cause_type="approval",
                cause_id=approval.id,
                reason="User rejected the proposed draft action.",
            )
            self.db.commit()
            return self.serialize_action(action)

        action.status = "APPROVED"
        self.db.flush()
        claimed = self.db.execute(
            update(Action)
            .where(Action.id == action.id, Action.status == "APPROVED")
            .values(status="EXECUTING", claimed_by="api-worker", claimed_at=now_utc())
        )
        if claimed.rowcount != 1:
            self.db.rollback()
            return self.serialize_action(action) | {"idempotent_replay": True}
        self.db.refresh(action)
        self._transition(
            version,
            "EXECUTING",
            cause_type="approval",
            cause_id=approval.id,
            reason="Action atomically claimed by one worker.",
        )
        action.result = {
            "draft_id": f"draft-{action.id[:8]}",
            "status": "CREATED",
            "recipient": action.arguments.get("recipient"),
            "idempotency_key": action.idempotency_key,
            "simulated": True,
        }
        action.status = "COMPLETED"
        action.completed_at = now_utc()
        self._transition(
            version,
            "COMPLETED",
            cause_type="tool",
            cause_id=action.id,
            reason="One simulated email draft was created; active cue indexes were pruned.",
            details={"result": action.result, "outcome_summary_created": True},
        )
        self.db.commit()
        return self.serialize_action(action)

    def advance_clock(self, duration: str = "PT48H") -> dict:
        hours = 48 if duration == "PT48H" else 1
        intention = self._current_intention()
        if not intention:
            raise KeyError("No demo intention")
        version = self._active_version(intention)
        key = digest(f"{version.intention_id}:{version.version}:ask-mark:absence-48h")
        existing = self.db.scalar(select(Action).where(Action.idempotency_key == key))
        if existing:
            return {"advanced_by": duration, "absence_fired": False, "action": self.serialize_action(existing)}
        window_start = datetime.fromisoformat(version.program["absence_rules"][0]["window"]["start"])
        legal_responses = self.db.scalars(
            select(Event).where(
                Event.channel == "legal", Event.event_type == "legal.response_received"
            )
        ).all()
        legal_response = next(
            (
                event
                for event in legal_responses
                if event.entity_keys.get("contract_id") == "contract-043"
                and event.occurred_at.replace(tzinfo=event.occurred_at.tzinfo or timezone.utc)
                >= window_start.replace(tzinfo=window_start.tzinfo or timezone.utc)
            ),
            None,
        )
        if legal_response:
            return {"advanced_by": duration, "absence_fired": False, "satisfied_by": legal_response.id}
        rule = version.program["absence_rules"][0]
        action = Action(
            version_id=version.id,
            action_id=rule["on_absence_action"]["action_id"],
            tool_id=rule["on_absence_action"]["tool_id"],
            arguments=rule["on_absence_action"]["arguments"],
            risk_tier="DRAFT",
            status="COMPLETED",
            idempotency_key=key,
            result={
                "draft_id": f"escalation-{uid()[:8]}",
                "status": "CREATED",
                "simulated": True,
            },
            completed_at=now_utc(),
        )
        self.db.add(action)
        job = self.db.scalar(
            select(MonitoringJob).where(
                MonitoringJob.version_id == version.id,
                MonitoringJob.job_type == "ABSENCE",
                MonitoringJob.status == "PENDING",
            )
        )
        if job:
            job.status = "DONE"
        self.db.add(
            StateTransition(
                version_id=version.id,
                from_state=version.status,
                to_state=version.status,
                cause_type="absence",
                cause_id="legal-response-48h",
                reason="No satisfying legal response was found in the 48-hour expectation window.",
                details={"advanced_hours": hours, "action": "ask-mark"},
            )
        )
        self.db.commit()
        return {"advanced_by": duration, "absence_fired": True, "action": self.serialize_action(action)}

    def list_intentions(self, user_id: str, status: str | None = None) -> list[dict]:
        query = select(Intention).where(Intention.user_id == user_id)
        if status:
            query = query.where(Intention.current_status == status)
        intentions = self.db.scalars(query.order_by(Intention.updated_at.desc())).all()
        return [self.serialize_intention_summary(i) for i in intentions]

    def serialize_intention_summary(self, intention: Intention) -> dict:
        version = self._active_version(intention)
        return {
            "intent_id": intention.id,
            "title": intention.title,
            "version": intention.active_version,
            "status": intention.current_status,
            "confidence": version.confidence,
            "channels": version.program.get("monitoring", {}).get("channels", []),
            "next_check_at": version.program.get("monitoring", {}).get("next_check_at"),
            "risk_tier": version.program.get("execution_policy", {}).get("risk_tier"),
            "updated_at": iso(intention.updated_at),
            "memory_tier": "HOT" if intention.current_status in ACTIVE_STATES else "AUDIT",
        }

    def serialize_intention(self, intention: Intention) -> dict:
        current = self._active_version(intention)
        versions = self.db.scalars(
            select(IntentionVersion)
            .where(IntentionVersion.intention_id == intention.id)
            .order_by(IntentionVersion.version.desc())
        ).all()
        transitions = self.db.scalars(
            select(StateTransition)
            .where(StateTransition.version_id.in_([v.id for v in versions]))
            .order_by(StateTransition.created_at.desc())
        ).all()
        actions = self.db.scalars(
            select(Action)
            .where(Action.version_id.in_([v.id for v in versions]))
            .order_by(Action.created_at.desc())
        ).all()
        return {
            **self.serialize_intention_summary(intention),
            "program": current.program,
            "readable_policy": {
                "waiting_for": ["Legal approval — contract-043 / v7", "Finance approval — deal-043"]
                if len(current.program["trigger"]["all"]) > 1
                else ["Legal approval — contract-043 / v7"],
                "blocked_when": ["The contract is closed", "The document is no longer v7"],
                "approval": "Required before creating the external email draft",
                "interruption": "Defer nonurgent alerts during the 09:00–11:00 focus block",
                "absence": "Draft an escalation to Mark after 48 hours without a legal response",
                "forgetting": "Remove from hot memory immediately after a terminal transition",
            },
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "status": v.status,
                    "created_at": iso(v.created_at),
                    "source_quote": v.program.get("source", {}).get("original_quote"),
                    "changed_fields": ["trigger.all", "monitoring.channels"] if v.version > 1 else [],
                }
                for v in versions
            ],
            "transitions": [self.serialize_transition(t) for t in transitions],
            "actions": [self.serialize_action(a) for a in actions],
        }

    def serialize_transition(self, transition: StateTransition) -> dict:
        return {
            "id": transition.id,
            "type": "transition",
            "from_state": transition.from_state,
            "to_state": transition.to_state,
            "cause_type": transition.cause_type,
            "cause_id": transition.cause_id,
            "reason": transition.reason,
            "details": transition.details,
            "created_at": iso(transition.created_at),
        }

    def serialize_evaluation(self, item: EventEvaluation | None) -> dict:
        if item is None:
            return {}
        event = self.db.get(Event, item.event_id)
        return {
            "id": item.id,
            "type": "evaluation",
            "event_id": item.event_id,
            "channel": event.channel if event else None,
            "event_type": event.event_type if event else None,
            "decision": item.decision,
            "reason": item.reason,
            "confidence": item.match_confidence,
            "candidate_rank": item.candidate_rank,
            "predicate_results": item.predicate_results,
            "context_tokens": item.context_tokens,
            "created_at": iso(item.created_at),
        }

    def serialize_action(self, action: Action) -> dict:
        return {
            "id": action.id,
            "type": "action",
            "action_id": action.action_id,
            "tool_id": action.tool_id,
            "arguments": action.arguments,
            "risk_tier": action.risk_tier,
            "status": action.status,
            "idempotency_key": action.idempotency_key,
            "result": action.result,
            "created_at": iso(action.created_at),
            "completed_at": iso(action.completed_at),
        }

    def pending_approvals(self) -> list[dict]:
        approvals = self.db.scalars(
            select(Approval).where(Approval.decision.is_(None)).order_by(Approval.requested_at.desc())
        ).all()
        result = []
        for approval in approvals:
            action = self.db.get(Action, approval.action_id)
            version = self.db.get(IntentionVersion, action.version_id) if action else None
            if action and version and action.status == "AWAITING_APPROVAL":
                result.append(
                    {
                        "approval_id": approval.id,
                        "requested_at": iso(approval.requested_at),
                        "expires_at": iso(approval.expires_at),
                        "action_hash": approval.action_hash,
                        "action": self.serialize_action(action),
                        "supporting_cues": ["Legal approved contract-043 / v7", "Finance approved deal-043"],
                        "inhibitors_checked": ["Contract is not closed", "Document version is current"],
                        "source_quote": version.program["source"]["original_quote"],
                    }
                )
        return result

    def timeline(self, limit: int = 100) -> list[dict]:
        transitions = self.db.scalars(
            select(StateTransition).order_by(StateTransition.created_at.desc()).limit(limit)
        ).all()
        evaluations = self.db.scalars(
            select(EventEvaluation).order_by(EventEvaluation.created_at.desc()).limit(limit)
        ).all()
        actions = self.db.scalars(select(Action).order_by(Action.created_at.desc()).limit(limit)).all()
        items = [self.serialize_transition(t) for t in transitions]
        items += [self.serialize_evaluation(e) for e in evaluations]
        items += [self.serialize_action(a) for a in actions]
        return sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)[:limit]

    def reset_demo(self) -> dict:
        # Demo mode is intentionally single-tenant; reset restores the published deterministic seed.
        for model in [
            Approval,
            Action,
            EventEvaluation,
            Event,
            StateTransition,
            CueIndex,
            MonitoringJob,
            IntentionVersion,
            Intention,
            Preference,
            Message,
            SessionRecord,
            User,
        ]:
            self.db.execute(delete(model))
        self.db.commit()
        request = MessageCreate(
            user_id="demo-user",
            session_id="session-a",
            client_request_id="seed-initial",
            content=PRIMARY_MESSAGE,
        )
        created = self.create_intention(request)
        intent_id = created["intention"]["intent_id"]
        self.revise_intention(
            intent_id,
            RevisionCreate(
                session_id="session-b",
                client_request_id="seed-revision",
                content=REVISION_MESSAGE,
            ),
        )
        return {
            "scenario_id": "contract-approval-official-demo",
            "intent_id": intent_id,
            "status": "DORMANT",
            "current_step": 0,
            "total_steps": 10,
            "clock": "2026-07-16T09:00:00-05:00",
        }
