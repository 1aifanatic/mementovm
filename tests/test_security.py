import asyncio
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.config import Settings
from backend.app.db import SessionLocal
from backend.app.domain.program import build_demo_program
from backend.app.main import app
from backend.app.models import Approval, now_utc
from backend.app.security import (
    SlidingWindowRateLimiter,
    authorize_event_ingestion,
    validate_event_size,
)
from backend.app.services.compiler import CompilerService
from backend.app.services.validator import validate_program


def test_production_event_ingestion_fails_closed():
    production = Settings(app_env="production", event_ingest_api_key="")
    with pytest.raises(HTTPException) as missing:
        authorize_event_ingestion(production, supplied_key=None, source="simulator")
    assert missing.value.status_code == 503

    configured = Settings(app_env="production", event_ingest_api_key="a-secure-event-key")
    with pytest.raises(HTTPException) as forged:
        authorize_event_ingestion(configured, supplied_key="wrong", source="webhook")
    assert forged.value.status_code == 401
    authorize_event_ingestion(
        configured, supplied_key="a-secure-event-key", source="webhook"
    )


def test_development_only_allows_unsigned_simulator_events():
    development = Settings(app_env="development", event_ingest_api_key="")
    authorize_event_ingestion(development, supplied_key=None, source="simulator")
    with pytest.raises(HTTPException) as forged:
        authorize_event_ingestion(development, supplied_key=None, source="external-webhook")
    assert forged.value.status_code == 401


def test_event_size_limit_and_rate_limit_are_deterministic():
    validate_event_size({"payload": "small"}, 100)
    with pytest.raises(HTTPException) as oversized:
        validate_event_size({"payload": "x" * 100}, 32)
    assert oversized.value.status_code == 413

    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("judge", now=0)
    assert limiter.allow("judge", now=1)
    assert not limiter.allow("judge", now=2)
    assert limiter.allow("judge", now=61)


def test_forged_event_is_rejected_by_public_api():
    with TestClient(app) as client:
        response = client.post(
            "/v1/events",
            json={
                "event_id": "forged-no-key",
                "source": "external-webhook",
                "channel": "legal",
                "event_type": "legal.approval_changed",
                "occurred_at": "2026-07-16T09:10:00-05:00",
                "entity_keys": {"contract_id": "contract-043"},
                "payload": {"approval": {"status": "APPROVED"}},
            },
        )
        assert response.status_code == 401


def test_expired_approval_cannot_execute():
    with TestClient(app) as client:
        client.post("/v1/simulator/reset")
        for step in [
            "legal_approval_current",
            "finance_approval_current",
        ]:
            response = client.post(
                f"/v1/simulator/scenarios/contract-approval-official-demo/steps/{step}"
            )
            assert response.status_code == 200
        approval_id = client.get("/v1/approvals/pending").json()["items"][0]["approval_id"]
        with SessionLocal() as db:
            approval = db.scalar(select(Approval).where(Approval.id == approval_id))
            approval.expires_at = now_utc() - timedelta(seconds=1)
            db.commit()

        response = client.post(
            f"/v1/approvals/{approval_id}/decision",
            json={"decision": "APPROVE", "decided_by": "security-test"},
        )
        assert response.status_code == 409
        assert "expired" in response.json()["detail"].lower()


class RepairingGateway:
    def __init__(self):
        self.repair_calls = 0

    async def compile_intention(self, **_: object):
        invalid = build_demo_program(
            intent_id="candidate",
            version=1,
            message_id="candidate-message",
            session_id="candidate-session",
            source_text="candidate",
        )
        invalid["action"]["tool_id"] = "shell.execute"
        return invalid, {"model": "qwen-test", "request_id": "compile-1", "usage": {}}

    async def repair_intention(self, **kwargs: object):
        self.repair_calls += 1
        repaired = dict(kwargs["candidate"])
        repaired["action"] = dict(repaired["action"])
        repaired["action"]["tool_id"] = "email.create_draft"
        return repaired, {"model": "qwen-test", "request_id": "repair-1", "usage": {}}


def test_qwen_compiler_repairs_once_then_validates():
    gateway = RepairingGateway()
    result = asyncio.run(
        CompilerService(
            Settings(dashscope_api_key="configured-for-mock"), gateway=gateway
        ).compile(
            content="When legal approves, prepare a draft.",
            intent_id="intent-test",
            message_id="message-test",
            session_id="session-test",
            user_id="demo-user",
            timezone_name="America/Chicago",
        )
    )
    assert gateway.repair_calls == 1
    assert result["model_metadata"]["repair_attempted"] is True
    assert validate_program(result) == []
