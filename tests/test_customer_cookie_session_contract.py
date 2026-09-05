from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL_HTML = ROOT / "frontend/customer/index.html"
COOKIE_SESSION = ROOT / "frontend/customer/cookie-session.js"


def test_customer_portal_loads_cookie_session_immediately_after_base_app():
    html = PORTAL_HTML.read_text(encoding="utf-8")
    app = html.index("/static/customer/app.js")
    cookie = html.index("/static/customer/cookie-session.js")
    enhancements = html.index("/static/customer/portal-enhancements.js")
    assert app < cookie < enhancements
    assert "cookie-session.js?v=20260905-5" in html


def test_customer_cookie_session_ignores_bearer_token_and_uses_same_origin_cookie():
    script = COOKIE_SESSION.read_text(encoding="utf-8")
    assert 'localStorage.setItem' not in script
    assert 'headers.Authorization' not in script
    assert 'Authorization' not in script
    assert 'credentials: "same-origin"' in script
    assert 'token = null' in script
    assert 'await startPortal()' in script


def test_customer_cookie_session_clears_legacy_browser_token():
    script = COOKIE_SESSION.read_text(encoding="utf-8")
    assert 'localStorage.removeItem("xvond_customer_token")' in script
