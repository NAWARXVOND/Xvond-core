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
