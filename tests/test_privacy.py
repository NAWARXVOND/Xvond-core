from backend.app.core.ai.base import AIResponse, ToolCall, ToolOutput
from backend.app.core.privacy import (
    protect_text,
    protect_tool_outputs,
    restore_ai_response,
    restore_text,
)


def test_protect_text_redacts_email_phone_and_numeric_identifier():
    original = "Email customer@example.com, call +968 9123 4567, ID 12345678"
    protected = protect_text(original)
    assert "customer@example.com" not in protected.text
    assert "+968 9123 4567" not in protected.text
    assert "12345678" not in protected.text
    assert "[XVOND_EMAIL_" in protected.text
    assert restore_text(protected.text, protected.replacements) == original


def test_restore_ai_response_restores_tool_arguments():
    protected = protect_text("Call +968 9123 4567")
    token = next(iter(protected.replacements))
    response = AIResponse(
        text=f"Using {token}",
        tool_calls=[
            ToolCall(
                id="call-1",
                name="action_request",
                arguments={"phone": token},
            )
        ],
    )
    restored = restore_ai_response(response, protected.replacements)
    assert restored.text == "Using +968 9123 4567"
    assert restored.tool_calls[0].arguments["phone"] == "+968 9123 4567"


def test_tool_outputs_are_redacted_before_external_provider_roundtrip():
    replacements = {}
    outputs = [
        ToolOutput(
            call_id="call-1",
            name="lookup",
            success=True,
            data={"email": "customer@example.com", "phone": "+968 9123 4567"},
        )
    ]
    protected = protect_tool_outputs(outputs, replacements)
    assert protected is not None
    assert "customer@example.com" not in str(protected[0].data)
    assert "+968 9123 4567" not in str(protected[0].data)
    assert replacements


def test_shared_mapping_keeps_same_value_consistent_across_prompt_parts():
    replacements = {}
    first = protect_text("customer@example.com", replacements)
    second = protect_text("Again customer@example.com", replacements)
    token = next(iter(replacements))
    assert first.text == token
    assert token in second.text
    assert len(replacements) == 1


def test_protect_text_does_not_guess_names():
    protected = protect_text("My name is Nawar")
    assert protected.text == "My name is Nawar"
    assert protected.replacements == {}
