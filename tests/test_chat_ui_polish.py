from backend.app.api.website_widget import DEFAULT_BEHAVIOR, WebsiteSetup


def test_website_setup_supports_bilingual_widget_copy():
    setup = WebsiteSetup(
        allowed_domain="xvond.com",
        welcome_message="مرحباً",
        welcome_message_en="Hello",
        launcher_label_ar="مساعد Xvond",
        launcher_label_en="Chat",
    )
    assert setup.welcome_message == "مرحباً"
    assert setup.welcome_message_en == "Hello"
    assert setup.launcher_label_ar == "مساعد Xvond"
    assert setup.launcher_label_en == "Chat"


def test_website_behavior_requests_plain_chat_text():
    assert "plain text" in DEFAULT_BEHAVIOR.lower()
    assert "markdown bold markers" in DEFAULT_BEHAVIOR.lower()


def test_admin_test_chat_contains_bidi_and_cleanup_guards():
    source = open("frontend/admin/test-chat-feedback.js", encoding="utf-8").read()
    assert "adminChatDirection" in source
    assert "unicode-bidi:plaintext" in source
    assert "adminChatCleanText" in source
    assert 'dir="${adminChatDirection(response)}"' in source


def test_website_widget_contains_page_language_and_bidi_guards():
    source = open("backend/app/api/website_widget.py", encoding="utf-8").read()
    assert "pageLang.startsWith('ar')" in source
    assert "unicode-bidi:plaintext" in source
    assert "__WELCOME_AR__" in source
    assert "__WELCOME_EN__" in source
    assert "cleanText(value)" in source


def test_website_widget_shows_and_clears_typing_indicator():
    source = open("backend/app/api/website_widget.py", encoding="utf-8").read()
    assert "function showTyping()" in source
    assert "function hideTyping()" in source
    assert "xvond-dot" in source
    assert "showTyping();send.disabled=true" in source
    assert "hideTyping();add(failureMessage" in source
    assert "finally{send.disabled=false;input.disabled=false" in source
