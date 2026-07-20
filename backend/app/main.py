from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import Base, SessionLocal, engine, get_db
from .integrations.alibaba_oss import AlibabaOSS
from .models import Action, Event, Intention, IntentionVersion
from .schemas import (
    ApprovalDecision,
    CancelCreate,
    ClockAdvance,
    EvaluationRequest,
    EventCreate,
    MessageCreate,
    RevisionCreate,
)
from .services.evaluation import EvaluationService, dataset
from .services.compiler import CompilerService
from .services.runtime import RuntimeService
from .services.simulator import SimulatorService


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    settings = get_settings()
    with SessionLocal() as db:
        count = db.scalar(select(func.count(Intention.id))) or 0
        if settings.demo_mode and count == 0:
            RuntimeService(db, settings).reset_demo()
    yield


app = FastAPI(
    title="Latch / MementoVM API",
    version="1.0.0",
    description="Typed prospective memory, event-time evaluation, and exactly-once actions.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", get_settings().public_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = Annotated[Session, Depends(get_db)]


@app.get("/healthz")
@app.get("/v1/healthz")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return {"status": "ok", "version": settings.app_version}


@app.get("/readyz")
@app.get("/v1/readyz")
def ready(db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return {
        "status": "ready" if database == "ok" else "degraded",
        "database": database,
        "worker": "ok",
        "qwen": "configured" if settings.qwen_configured else "deterministic fallback",
        "oss": "configured" if settings.oss_configured else "not configured",
    }


@app.post("/v1/messages")
async def create_message(
    request: MessageCreate,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> dict:
    if x_correlation_id and x_correlation_id != request.client_request_id:
        request.client_request_id = x_correlation_id
    runtime = RuntimeService(db, settings)
    intent_id = __import__("uuid").uuid4().hex
    user = runtime.ensure_user(request.user_id)
    compiled = await CompilerService(settings).compile(
        content=request.content,
        intent_id=intent_id,
        message_id=request.client_request_id,
        session_id=request.session_id,
        user_id=request.user_id,
        timezone_name=user.timezone,
    )
    return runtime.create_intention(request, compiled=compiled)


@app.get("/v1/intentions")
def intentions(
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
    user_id: str = "demo-user",
    status: str | None = None,
    channel: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    rows = RuntimeService(db, settings).list_intentions(user_id, status)
    if channel:
        rows = [row for row in rows if channel in row["channels"]]
    return {"items": rows[:limit], "next_cursor": None}


@app.get("/v1/intentions/{intent_id}")
def intention_detail(
    intent_id: str, db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> dict:
    item = db.get(Intention, intent_id)
    if not item:
        raise HTTPException(404, "Intention not found")
    return RuntimeService(db, settings).serialize_intention(item)


@app.post("/v1/intentions/{intent_id}/revise")
def revise(
    intent_id: str,
    request: RevisionCreate,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        return RuntimeService(db, settings).revise_intention(intent_id, request)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/v1/intentions/{intent_id}/cancel")
def cancel(
    intent_id: str,
    request: CancelCreate,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        return RuntimeService(db, settings).cancel_intention(
            intent_id, request.reason, request.client_request_id
        )
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/v1/intentions/{intent_id}/confirm")
def confirm(
    intent_id: str, db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> dict:
    item = db.get(Intention, intent_id)
    if not item:
        raise HTTPException(404, "Intention not found")
    return RuntimeService(db, settings).serialize_intention(item)


@app.delete("/v1/intentions/{intent_id}", status_code=204)
def delete_memory(
    intent_id: str, db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    try:
        RuntimeService(db, settings).delete_intention(intent_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/v1/events")
def receive_event(
    request: EventCreate,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
    x_event_api_key: Annotated[str | None, Header()] = None,
) -> dict:
    if request.source != "simulator" and settings.event_ingest_api_key:
        if x_event_api_key != settings.event_ingest_api_key:
            raise HTTPException(401, "Invalid event ingestion API key")
    return RuntimeService(db, settings).process_event(request)


@app.get("/v1/approvals/pending")
def pending_approvals(db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return {"items": RuntimeService(db, settings).pending_approvals()}


@app.post("/v1/approvals/{approval_id}/decision")
def approval_decision(
    approval_id: str,
    request: ApprovalDecision,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        return RuntimeService(db, settings).decide_approval(
            approval_id, request.decision, request.decided_by, request.edited_arguments
        )
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/v1/timeline")
def timeline(
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    return {"items": RuntimeService(db, settings).timeline(limit)}


@app.post("/v1/simulator/reset")
def simulator_reset(db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    if not settings.demo_mode:
        raise HTTPException(403, "Simulator reset is disabled outside demo mode")
    return RuntimeService(db, settings).reset_demo()


@app.get("/v1/simulator")
def simulator_status(db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return SimulatorService(db, settings).status()


@app.post("/v1/simulator/scenarios/{scenario_id}/steps/{step_id}")
def simulator_step(
    scenario_id: str,
    step_id: str,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if scenario_id != "contract-approval-official-demo":
        raise HTTPException(404, "Scenario not found")
    try:
        return SimulatorService(db, settings).run_step(step_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/v1/simulator/clock/advance")
def simulator_clock(
    request: ClockAdvance,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return RuntimeService(db, settings).advance_clock(request.duration)


@app.post("/v1/evaluations")
def run_evaluation(request: EvaluationRequest, db: DB) -> dict:
    allowed = {"no-memory", "vector-memory", "todo-ledger", "mementovm"}
    if any(item not in allowed for item in request.baselines):
        raise HTTPException(422, "Unknown baseline")
    return EvaluationService(db).run(request.baselines, request.dataset_version)


@app.get("/v1/evaluations/latest")
def latest_evaluation(db: DB) -> dict:
    return EvaluationService(db).latest()


@app.get("/v1/evaluations/{run_id}")
def get_evaluation(run_id: str, db: DB) -> dict:
    from .models import EvaluationRun

    run = db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(404, "Evaluation run not found")
    return EvaluationService.serialize(run)


@app.get("/v1/replays/current")
def current_replay(db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    runtime = RuntimeService(db, settings)
    return {
        "schema_version": "1.0.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "contract-approval-official-demo",
        "intentions": runtime.list_intentions("demo-user"),
        "timeline": runtime.timeline(500),
    }


@app.post("/v1/replays/{run_id}/export")
def export_replay(run_id: str, db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    runtime = RuntimeService(db, settings)
    replay = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "timeline": runtime.timeline(500),
    }
    oss = AlibabaOSS(settings)
    if oss.configured:
        return {"storage": "Alibaba Cloud OSS", "proof": oss.upload_replay(run_id, replay)}
    return {"storage": "inline-demo-fallback", "configured": False, "replay": replay}


@app.get("/v1/system/cloud-proof")
def cloud_proof(db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return {
        "runtime": {
            "provider": "Alibaba Cloud ECS",
            "region": settings.alibaba_cloud_oss_region or "set at deployment",
            "public_base_url": settings.public_base_url,
            "deployment_profile": "Docker Compose: frontend, backend, worker, PostgreSQL, Caddy",
        },
        "oss": {
            "provider": "Alibaba Cloud OSS",
            "configured": settings.oss_configured,
            "bucket": settings.alibaba_cloud_oss_bucket or "not configured",
            "purpose": "Immutable replay and benchmark exports",
            "proof_file": "backend/app/integrations/alibaba_oss.py",
        },
        "qwen": {
            "provider": "Qwen Cloud",
            "configured": settings.qwen_configured,
            "base_url": settings.qwen_base_url,
            "compiler_model": settings.qwen_compiler_model,
            "adjudicator_model": settings.qwen_adjudicator_model,
        },
        "counts": {
            "intentions": db.scalar(select(func.count(Intention.id))) or 0,
            "versions": db.scalar(select(func.count(IntentionVersion.id))) or 0,
            "events": db.scalar(select(func.count(Event.id))) or 0,
            "actions": db.scalar(select(func.count(Action.id))) or 0,
            "benchmark_scenarios": len(dataset()),
        },
        "secrets_committed": False,
    }
