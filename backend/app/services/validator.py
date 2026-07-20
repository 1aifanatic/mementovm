import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path(__file__).parents[1] / "domain" / "schemas" / "intention-program-v1.json"
ALLOWED_TOOLS = {"email.create_draft", "notification.create_internal_draft"}


@lru_cache
def intention_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_program(program: dict) -> list[str]:
    validator = Draft202012Validator(intention_schema(), format_checker=FormatChecker())
    errors = [f"{'.'.join(str(part) for part in error.path) or '$'}: {error.message}" for error in validator.iter_errors(program)]
    action = program.get("action", {})
    if action.get("tool_id") not in ALLOWED_TOOLS:
        errors.append("action.tool_id: tool is not allowlisted")
    policy = program.get("execution_policy", {})
    if policy.get("risk_tier") in {"EXTERNAL_WRITE", "FINANCIAL", "DESTRUCTIVE"} and policy.get("approval") != "REQUIRED":
        errors.append("execution_policy.approval: high-risk action must require approval")
    if program.get("unresolved_fields") and policy.get("approval") == "NOT_REQUIRED":
        errors.append("unresolved_fields: ambiguous program cannot auto-execute")
    return errors

