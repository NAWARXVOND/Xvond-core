from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

# ============================================================
# API Routers
# ============================================================

from backend.app.api.auth import router as auth_router
from backend.app.api.users import router as users_router

from backend.app.api.admin import router as admin_router
from backend.app.api.admin_ai import router as admin_ai_router
from backend.app.api.admin_audit import router as admin_audit_router
from backend.app.api.admin_billing import router as admin_billing_router
from backend.app.api.admin_business import router as admin_business_router
from backend.app.api.admin_channels import router as admin_channels_router
from backend.app.api.admin_company_view import router as admin_company_view_router
from backend.app.api.admin_dashboard import router as admin_dashboard_router
from backend.app.api.admin_integrations import router as admin_integrations_router
from backend.app.api.admin_knowledge import router as admin_knowledge_router
from backend.app.api.admin_operations import router as admin_operations_router
from backend.app.api.admin_production import router as admin_production_router
from backend.app.api.admin_providers import router as admin_providers_router
from backend.app.api.admin_setup import router as admin_setup_router
from backend.app.api.admin_tool_execution import router as admin_tool_execution_router
from backend.app.api.admin_tools import router as admin_tools_router

from backend.app.api.agent_factory import router as agent_factory_router
from backend.app.api.ai_agents import router as ai_agents_router

from backend.app.api.company_modules import router as company_modules_router
from backend.app.api.customer_agents import router as customer_agents_router
from backend.app.api.customer_business import router as customer_business_router
from backend.app.api.customer_portal import router as customer_portal_router

from backend.app.api.modules import router as modules_router
from backend.app.api.usage import router as usage_router
from backend.app.api.whatsapp_webhook import router as whatsapp_webhook_router

# ============================================================
# Core
# ============================================================

from backend.app.core.config.settings import settings
from backend.app.core.database.connection import SessionLocal
from backend.app.core.module_loader import discover_modules
from backend.app.core.module_manager import module_manager
from backend.app.core.rate_limit import rate_limiter


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


# ============================================================
# Application startup
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Discover modules at startup.
    #
    # Existing Xvond behavior is intentionally preserved:
    # discovered modules are installed and enabled.
    #
    # module_loader already prevents test_module from being
    # discovered in production.
    for module in discover_modules():
        module_manager.install(module)
        module_manager.enable(
            module.name
        )

    yield


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


_RATE_LIMITS = {
    ("POST", "/auth/login"): (10, 60),
    ("POST", "/auth/customer/forgot-password"): (5, 300),
    ("POST", "/auth/customer/reset-password"): (10, 300),
    ("POST", "/webhooks/whatsapp"): (240, 60),
}


@app.middleware("http")
async def protect_public_endpoints(request: Request, call_next):
    rule = _RATE_LIMITS.get(
        (request.method.upper(), request.url.path)
    )

    if rule is None and (
        request.method.upper() == "POST"
        and request.url.path.startswith("/ai-agents/")
        and request.url.path.endswith("/chat")
    ):
        rule = (60, 60)

    if rule is not None:
        forwarded = request.headers.get("x-forwarded-for", "")
        client_ip = (
            forwarded.split(",", 1)[0].strip()
            or request.headers.get("cf-connecting-ip", "").strip()
            or (request.client.host if request.client else "unknown")
        )
        limit, window = rule
        key = f"{client_ip}:{request.method}:{request.url.path}"

        if not rate_limiter.allow(key, limit, window):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(window)},
            )

    return await call_next(request)


# ============================================================
# Routers - Authentication / Users
# ============================================================

app.include_router(auth_router)
app.include_router(users_router)


# ============================================================
# Routers - Xvond Admin
# ============================================================

app.include_router(admin_router)
app.include_router(admin_ai_router)
app.include_router(admin_audit_router)
app.include_router(admin_billing_router)
app.include_router(admin_business_router)
app.include_router(admin_channels_router)
app.include_router(admin_company_view_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_integrations_router)
app.include_router(admin_knowledge_router)
app.include_router(admin_operations_router)
app.include_router(admin_production_router)
app.include_router(admin_providers_router)
app.include_router(admin_setup_router)
app.include_router(admin_tool_execution_router)
app.include_router(admin_tools_router)


# ============================================================
# Routers - Agent Platform
# ============================================================

app.include_router(agent_factory_router)
app.include_router(ai_agents_router)


# ============================================================
# Routers - Modules
# ============================================================

app.include_router(modules_router)
app.include_router(company_modules_router)


# ============================================================
# Routers - Customer
# ============================================================

app.include_router(customer_agents_router)
app.include_router(customer_business_router)
app.include_router(customer_portal_router)
app.include_router(usage_router)


# ============================================================
# Routers - Public Webhooks
# ============================================================

app.include_router(
    whatsapp_webhook_router
)


# ============================================================
# Static frontend
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(
            FRONTEND_DIR
        )
    ),
    name="static",
)


# ============================================================
# System endpoints
# ============================================================

@app.get("/")
def root():

    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
    }


@app.get("/health")
def health():

    db = SessionLocal()

    try:

        db.execute(
            text("SELECT 1")
        )

        return {
            "status": "healthy",
            "database": "ok",
            "environment":
                settings.APP_ENV,
            "version":
                settings.APP_VERSION,
        }

    finally:
        db.close()


# ============================================================
# UI redirects
# ============================================================

@app.get("/admin-ui")
def admin_ui():

    return RedirectResponse(
        url="/static/admin/index.html"
    )


@app.get("/customer-ui")
def customer_ui():

    return RedirectResponse(
        url="/static/customer/index.html"
    )
