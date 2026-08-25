from backend.app.modules.solutions.catalog import (
    AI_EMPLOYEE_CAPABILITIES,
    AI_EMPLOYEE_CHANNELS,
    PACKAGE_TIERS,
    SERVICE_CATALOG,
    public_catalog,
)


def test_xvond_service_catalog_has_dashboard_builders():
    assert set(SERVICE_CATALOG) == {
        "ai_agents",
        "automation",
        "analytics",
        "integrations",
    }
    assert all(
        item["delivery_mode"] == "builder"
        for item in SERVICE_CATALOG.values()
    )


def test_ai_employee_catalog_supports_requested_delivery():
    assert {"customer_service", "booking", "orders", "human_handoff"} <= set(
        AI_EMPLOYEE_CAPABILITIES
    )
    assert {"whatsapp", "voice", "website"} <= set(AI_EMPLOYEE_CHANNELS)


def test_public_catalog_is_json_ready():
    result = public_catalog()
    assert len(result["services"]) == 4
    assert {item["code"] for item in result["services"]} == set(SERVICE_CATALOG)
    assert {item["code"] for item in result["package_tiers"]} == set(PACKAGE_TIERS)
