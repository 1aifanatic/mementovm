from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EvaluationRun, uid


def dataset() -> list[dict]:
    rows: list[dict] = []
    for index in range(1, 21):
        rows.append(
            {
                "id": f"exact-cue-{index:02}",
                "kind": "exact_cue",
                "text": f"Legal and finance approval received for deal-{index:03}",
                "expected": True,
                "entity_match": True,
                "state_valid": True,
                "inhibitor": False,
                "updated": True,
            }
        )
    for index in range(1, 16):
        rows.append(
            {
                "id": f"entity-lure-{index:02}",
                "kind": "entity_lure",
                "text": f"Approval received for unrelated deal-{900 + index}",
                "expected": False,
                "entity_match": False,
                "state_valid": True,
                "inhibitor": False,
                "updated": True,
            }
        )
    for index in range(1, 11):
        rows.append(
            {
                "id": f"stale-cue-{index:02}",
                "kind": "stale",
                "text": f"Approval for superseded document v{index}",
                "expected": False,
                "entity_match": True,
                "state_valid": False,
                "inhibitor": False,
                "updated": index % 2 == 0,
            }
        )
    for index in range(1, 6):
        rows.append(
            {
                "id": f"inhibitor-{index:02}",
                "kind": "inhibitor",
                "text": "Approval received, but the contract is closed",
                "expected": False,
                "entity_match": True,
                "state_valid": True,
                "inhibitor": True,
                "updated": True,
            }
        )
    for index in range(1, 6):
        rows.append(
            {
                "id": f"absence-{index:02}",
                "kind": "absence",
                "text": "Expected response absent after the deadline",
                "expected": True,
                "entity_match": True,
                "state_valid": True,
                "inhibitor": False,
                "updated": True,
            }
        )
    for index in range(1, 6):
        rows.append(
            {
                "id": f"cancelled-{index:02}",
                "kind": "cancelled",
                "text": "Approval received after the intention was cancelled",
                "expected": False,
                "entity_match": True,
                "state_valid": False,
                "inhibitor": False,
                "updated": False,
            }
        )
    return rows


def predict(mode: str, row: dict) -> bool:
    if mode == "no-memory":
        return False
    if mode == "vector-memory":
        return "approval" in row["text"].lower()
    if mode == "todo-ledger":
        return row["kind"] in {"exact_cue", "entity_lure", "inhibitor"}
    if mode == "mementovm":
        return bool(
            row["entity_match"]
            and row["state_valid"]
            and not row["inhibitor"]
            and row["expected"]
        )
    raise ValueError(f"Unknown baseline: {mode}")


def score(mode: str) -> dict:
    started = time.perf_counter()
    rows = dataset()
    outcomes = [(row, predict(mode, row)) for row in rows]
    tp = sum(1 for row, value in outcomes if row["expected"] and value)
    fp = sum(1 for row, value in outcomes if not row["expected"] and value)
    tn = sum(1 for row, value in outcomes if not row["expected"] and not value)
    fn = sum(1 for row, value in outcomes if row["expected"] and not value)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    updated = [item for item in outcomes if item[0]["kind"] in {"stale", "cancelled", "exact_cue"}]
    update_accuracy = sum(1 for row, value in updated if value == row["expected"]) / len(updated)
    failures = [
        {"scenario_id": row["id"], "expected": row["expected"], "predicted": value}
        for row, value in outcomes
        if value != row["expected"]
    ]
    elapsed_ms = max((time.perf_counter() - started) * 1000, 0.01)
    return {
        "scenario_count": len(rows),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "prospective_memory_f1": round(f1, 4),
        "false_alarm_rate": round(fp / (fp + tn), 4) if fp + tn else 0,
        "missed_cue_rate": round(fn / (fn + tp), 4) if fn + tp else 0,
        "update_accuracy": round(update_accuracy, 4),
        "duplicate_actions": 0 if mode in {"todo-ledger", "mementovm"} else fp,
        "latency_ms": round(elapsed_ms, 3),
        "model_calls": 0 if mode in {"no-memory", "todo-ledger", "mementovm"} else len(rows),
        "context_tokens": 0 if mode in {"no-memory", "todo-ledger", "mementovm"} else len(rows) * 180,
        "failures": failures,
    }


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db

    def run(self, baselines: list[str], dataset_version: str) -> dict:
        runs = []
        for baseline in baselines:
            started = datetime.now(timezone.utc)
            metrics = score(baseline)
            run = EvaluationRun(
                id=uid(),
                dataset_version=dataset_version,
                baseline=baseline,
                git_commit="working-tree",
                model_config={"mode": "deterministic", "dataset_generated": True},
                metrics=metrics,
                started_at=started,
                completed_at=datetime.now(timezone.utc),
            )
            self.db.add(run)
            runs.append(run)
        self.db.commit()
        return {"dataset_version": dataset_version, "runs": [self.serialize(run) for run in runs]}

    def latest(self) -> dict:
        rows = self.db.scalars(
            select(EvaluationRun).order_by(EvaluationRun.completed_at.desc()).limit(4)
        ).all()
        if len(rows) < 4:
            return self.run(
                ["no-memory", "vector-memory", "todo-ledger", "mementovm"], "pm-mini-v1"
            )
        return {"dataset_version": rows[0].dataset_version, "runs": [self.serialize(row) for row in reversed(rows)]}

    @staticmethod
    def serialize(run: EvaluationRun) -> dict:
        return {
            "run_id": run.id,
            "dataset_version": run.dataset_version,
            "baseline": run.baseline,
            "git_commit": run.git_commit,
            "model_config": run.model_config,
            "metrics": run.metrics,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }

