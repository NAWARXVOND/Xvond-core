from pathlib import Path


def test_customer_agents_router_is_registered_in_main_app():
    root = Path(__file__).resolve().parents[1]
    source = (root / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "from backend.app.api.customer_agents import router as customer_agents_router" in source
    assert "customer_agents_router," in source
