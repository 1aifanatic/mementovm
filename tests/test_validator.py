from backend.app.domain.program import build_demo_program
from backend.app.services.validator import validate_program


def program() -> dict:
    return build_demo_program(
        intent_id="validator-intent",
        version=1,
        message_id="validator-message",
        session_id="validator-session",
        source_text="When legal approves, prepare a draft.",
    )


def test_unknown_tool_is_quarantined_by_policy_validation():
    candidate = program()
    candidate["action"]["tool_id"] = "browser.execute_arbitrary_script"
    assert any("not allowlisted" in error for error in validate_program(candidate))


def test_external_write_cannot_disable_approval():
    candidate = program()
    candidate["execution_policy"]["approval"] = "NOT_REQUIRED"
    assert any("must require approval" in error for error in validate_program(candidate))


def test_schema_rejects_unknown_top_level_fields():
    candidate = program()
    candidate["model_secret_reasoning"] = "never persist hidden reasoning"
    assert validate_program(candidate)
