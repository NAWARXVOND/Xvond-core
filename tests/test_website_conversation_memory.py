import inspect

from backend.app.api.website_widget import widget_js
from backend.app.core.config.settings import settings


def test_website_widget_persists_conversation_across_browser_sessions():
    source = inspect.getsource(widget_js)

    assert "localStorage.getItem(CID_KEY)" in source
    assert "localStorage.getItem(TOKEN_KEY)" in source
    assert "sessionStorage" not in source
    assert "let lastId=0" in source
    assert "const restoring=lastId===0" in source
    assert "if(m.role==='user')add(m.content,'xvond-u')" in source
    assert "m.role==='assistant'||m.role==='human'" in source
    assert "poll();" in source


def test_website_visitor_token_default_supports_long_lived_continuity():
    assert settings.WEBSITE_VISITOR_TOKEN_TTL_SECONDS >= 30 * 24 * 60 * 60
