from backend.app.modules.solutions.catalog import (
    AI_EMPLOYEE_CAPABILITIES,
    AI_EMPLOYEE_CHANNELS,
    SERVICE_CATALOG,
    public_catalog,
)


def test_xvond_service_catalog_has_all_business_services():
    assert set(SERVICE_CATALOG) == {
        "strategy",
        "ai_agents",
        "automation",
        "analytics",
        "custom_ai",
        "integrations",
        "marketing",
        "support",
    }


def test_ai_employee_catalog_supports_requested_delivery():
    assert {"customer_service", "booking", "orders", "human_handoff"} <= set(
        AI_EMPLOYEE_CAPABILITIES
    )
    assert {"whatsapp", "voice", "website"} <= set(AI_EMPLOYEE_CHANNELS)


def test_public_catalog_is_json_ready():
    result = public_catalog()
    assert len(result["services"]) == 8
    assert result["package_tiers"]
