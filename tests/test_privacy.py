from backend.app.core.ai.base import AIResponse, ToolCall
from backend.app.core.privacy import protect_text, restore_ai_response, restore_text


def test_protect_text_redacts_email_phone_and_high_confidence_id():
    original = "Email customer@example.com, call +968 9123 4567, ID 12345678"
    protected = protect_text(original)
    assert "customer@example.com" not in protected.text
    assert "+968 9123 4567" not in protected.text
    assert "12345678" not in protected.text
    assert "[XVOND_EMAIL_" in protected.text
    assert "[XVOND_PHONE_" in protected.text
    assert "[XVOND_ID_" in protected.text
    assert restore_text(protected.text, protected.replacements) == original


def test_restore_ai_response_restores_tool_arguments():
    protected = protect_text("Call +968 9123 4567")
    phone_token = next(
        token for token in protected.replacements if token.startswith("[XVOND_PHONE_")
    )
    response = AIResponse(
        text=f"Using {phone_token}",
        tool_calls=[
            ToolCall(
                id="call-1",
                name="action_request",
                arguments={"phone": phone_token},
            )
        ],
    )
    restored = restore_ai_response(response, protected.replacements)
    assert restored.text == "Using +968 9123 4567"
    assert restored.tool_calls[0].arguments["phone"] == "+968 9123 4567"


def test_protect_text_does_not_guess_names():
    protected = protect_text("My name is Nawar")
    assert protected.text == "My name is Nawar"
    assert protected.replacements == {}
