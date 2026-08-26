import backend.app.main as main_module
from fastapi.routing import APIRouter


app = main_module.app


def _normalized_path(path: str | None) -> str | None:
    if not path:
        return path
    if path == "/":
        return path
    return path.rstrip("/")


def _declared_router_operations():
    """Collect operations from the APIRouters explicitly mounted by main.py.

    FastAPI 0.137+ keeps included routers as lazy _IncludedRouter nodes inside
    app.routes, so app.routes is no longer a flat list of final APIRoute items.
    Inspecting the source APIRouters remains stable for duplicate detection.
    """
    operations = []
    seen_router_ids = set()

    for name, value in vars(main_module).items():
        if not name.endswith("_router") or not isinstance(value, APIRouter):
            continue
        if id(value) in seen_router_ids:
            continue
        seen_router_ids.add(id(value))

        for route in value.routes:
            path = _normalized_path(getattr(route, "path", None))
            methods = getattr(route, "methods", None) or set()
            if not path:
                continue
            for method in methods - {"HEAD", "OPTIONS"}:
                operations.append((method, path))

    return operations


def test_no_duplicate_api_routes():
    seen = set()
    duplicates = []

    for operation in _declared_router_operations():
        if operation in seen:
            duplicates.append(operation)
        seen.add(operation)

    assert duplicates == []


def test_customer_operations_routes_are_registered():
    # OpenAPI is the supported, effective route surface. It correctly traverses
    # FastAPI's lazy included-router tree on FastAPI 0.137+.
    paths = app.openapi().get("paths", {})

    assert "get" in paths.get("/customer/action-requests", {})
    assert "get" in paths.get("/customer/business/handoffs", {})
    assert "get" in paths.get("/customer/inbox", {})


def test_xvond_admin_does_not_expose_customer_content_routes():
    paths = app.openapi().get("paths", {})

    blocked = {
        "/admin/agent-actions/companies/{company_id}/requests",
        "/admin/agent-actions/requests/{request_id}",
        "/admin/operations/companies/{company_id}/conversations",
        "/admin/operations/companies/{company_id}/conversations/{conversation_id}",
        "/admin/handoff/companies/{company_id}/sessions",
        "/admin/handoff/companies/{company_id}/conversations/{conversation_id}/take-over",
        "/admin/handoff/companies/{company_id}/conversations/{conversation_id}/return-ai",
        "/admin/handoff/companies/{company_id}/conversations/{conversation_id}/message",
    }

    assert blocked.isdisjoint(paths)
