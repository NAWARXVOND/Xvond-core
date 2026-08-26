from backend.app.main import app


def test_no_duplicate_api_routes():
    seen = set()
    duplicates = []

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()

        if not path:
            continue

        for method in methods - {"HEAD", "OPTIONS"}:
            key = (method, path)

            if key in seen:
                duplicates.append(key)

            seen.add(key)

    assert duplicates == []


def _normalized_path(path: str | None) -> str | None:
    if not path:
        return path
    if path == "/":
        return path
    return path.rstrip("/")


def test_customer_operations_routes_are_registered():
    registered = {
        (method, _normalized_path(getattr(route, "path", None)))
        for route in app.routes
        for method in (getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/customer/action-requests") in registered
    assert ("GET", "/customer/business/handoffs") in registered
