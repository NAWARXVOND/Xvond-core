from pathlib import Path


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def test_auth_issues_httponly_same_site_cookie_and_keeps_api_bearer_compatibility():
    auth = source("backend/app/api/auth.py")
    dependencies = source("backend/app/core/dependencies.py")
    assert 'SESSION_COOKIE_NAME = "xvond_session"' in dependencies
    assert "HTTPBearer(auto_error=False)" in dependencies
    assert "request.cookies.get(SESSION_COOKIE_NAME)" in dependencies
    assert "httponly=True" in auth
    assert 'samesite="lax"' in auth
    assert "secure=settings.is_production" in auth
    assert '"access_token": token' in auth


def test_admin_ui_does_not_persist_bearer_token_in_browser_storage():
    admin = source("frontend/admin/app.js")
    assert 'localStorage.removeItem("xvond_admin_token")' in admin
    assert "localStorage.setItem(\"xvond_admin_token\"" not in admin
    assert 'credentials:"same-origin"' in admin
    assert "resumeAdminSession" in admin


def test_customer_portal_bootstraps_cookie_session_before_legacy_app_code():
    index = source("frontend/customer/index.html")
    session = source("frontend/customer/session-security.js")
    cleanup = '<script>localStorage.removeItem("xvond_customer_token");</script>'
    assert cleanup in index
    assert index.index(cleanup) < index.index('/static/customer/app.js')
    assert index.index('/static/customer/session-security.js') > index.index('/static/customer/app.js')
    assert 'localStorage.removeItem("xvond_customer_token")' in session
    assert 'credentials: "same-origin"' in session
    assert "token = null" in session
    assert "startPortal();" in session


def test_public_cors_does_not_allow_cross_origin_credentials():
    main = source("backend/app/main.py")
    assert 'allow_origins=["*"]' in main
    assert "allow_credentials=False" in main
