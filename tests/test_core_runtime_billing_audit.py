from decimal import Decimal

from backend.app.api.admin_service_billing import ServiceSubscriptionInput, _plain_decimal, _validated_limits
from backend.app.core.ai.response_language import apply_response_language, response_language_instruction
from backend.app.core.customer_runtime_policy import safe_service_unavailable_message


def test_auto_language_enforces_current_english_message_over_arabic_context():
    system = "Reply language policy: auto.\nDialect policy: levantine."
    user = (
        "COMPANY KNOWLEDGE:\nالخدمات والأسعار بالعربي\n\n"
        "CONVERSATION HISTORY:\nassistant: أهلاً وسهلاً\n\n"
        "CURRENT CUSTOMER MESSAGE (answer this intent directly):\nHello, I need help with my booking"
    )
    instruction = response_language_instruction(system, user)
    assert "English" in instruction
    assert "Do not switch to Arabic" in instruction
    assert apply_response_language(system, user).endswith(instruction)


def test_fixed_arabic_employee_policy_overrides_english_message():
    system = "Reply language policy: Arabic.\nDialect policy: gulf."
    instruction = response_language_instruction(system, "Hello, can you help me?")
    assert "Arabic" in instruction
    assert "configured Arabic dialect" in instruction


def test_safe_service_error_uses_employee_language_policy():
    assert safe_service_unavailable_message(
        "Reply language policy: English.", "مرحبا"
    ).startswith("Sorry")
    assert safe_service_unavailable_message(
        "Reply language policy: Arabic.", "Hello"
    ).startswith("عذرًا")


def test_large_plan_limits_are_not_serialized_in_scientific_notation():
    assert _plain_decimal(Decimal("1E+9")) == "1000000000"
    assert _validated_limits({"tokens": "1E+9"})["tokens"] == "1000000000"


def test_plan_save_does_not_implicitly_renew():
    payload = ServiceSubscriptionInput(plan_id=3)
    assert payload.renew is False


def test_admin_billing_fix_layer_is_loaded_last():
    html = open("frontend/admin/index.html", encoding="utf-8").read()
    assert "/static/admin/core-audit-fixes.js" in html
    assert html.rfind("core-audit-fixes.js") > html.rfind("control-center-polish.js")


def test_billing_ui_distinguishes_capacity_from_service_blocking_limit():
    source = open("frontend/admin/core-audit-fixes.js", encoding="utf-8").read()
    assert "Capacity full" in source
    assert "Plans are alternatives for each service, not simultaneous packages" in source
    assert "renewWorkspaceService" in source
    assert "All available services are already assigned" in source
