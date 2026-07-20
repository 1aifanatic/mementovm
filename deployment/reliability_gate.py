"""Run the complete judge scenario repeatedly against a live deployment."""

from __future__ import annotations

import argparse
import json
import urllib.request


def request(base_url: str, path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    call = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(call, timeout=30) as response:
        return json.loads(response.read())


def run_once(base_url: str, run_number: int) -> dict:
    reset = request(base_url, "/v1/simulator/reset", method="POST", body={})
    intent_id = reset["intent_id"]
    scenario = "/v1/simulator/scenarios/contract-approval-official-demo/steps"
    for step in [
        "lure_marketing_approval",
        "lure_old_rejection",
        "legal_approval_current",
        "unrelated_finance",
        "focus_block_start",
        "finance_approval_current",
        "focus_block_end",
    ]:
        request(base_url, f"{scenario}/{step}", method="POST", body={})

    approvals = request(base_url, "/v1/approvals/pending")["items"]
    if len(approvals) != 1:
        raise AssertionError(f"run {run_number}: expected one approval, got {len(approvals)}")
    approval_id = approvals[0]["approval_id"]
    executed = request(
        base_url,
        f"/v1/approvals/{approval_id}/decision",
        method="POST",
        body={"decision": "APPROVE", "decided_by": "reliability-gate"},
    )
    if executed["status"] != "COMPLETED":
        raise AssertionError(f"run {run_number}: primary draft did not complete")

    duplicate = request(
        base_url,
        f"{scenario}/duplicate_finance_event",
        method="POST",
        body={},
    )["result"]
    if not duplicate["deduplicated"]:
        raise AssertionError(f"run {run_number}: duplicate event was not suppressed")
    absence = request(
        base_url,
        f"{scenario}/advance_absence_clock",
        method="POST",
        body={},
    )["result"]
    if not absence["absence_fired"]:
        raise AssertionError(f"run {run_number}: absence rule did not fire")

    detail = request(base_url, f"/v1/intentions/{intent_id}")
    primary = [action for action in detail["actions"] if action["action_id"] == "prepare-redline-draft"]
    if detail["status"] != "COMPLETED" or len(primary) != 1:
        raise AssertionError(f"run {run_number}: terminal state or exactly-once invariant failed")
    return {
        "run": run_number,
        "intent_id": intent_id,
        "status": detail["status"],
        "primary_drafts": len(primary),
        "absence_fired": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    results = [run_once(args.base_url, run_number) for run_number in range(1, args.runs + 1)]
    print(json.dumps({"passed": len(results), "failed": 0, "results": results}, indent=2))


if __name__ == "__main__":
    main()
