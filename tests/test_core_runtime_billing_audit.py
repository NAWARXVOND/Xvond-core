from decimal import Decimal

from fastapi import HTTPException

from backend.app.api.admin_service_billing import ServiceSubscriptionInput, _plain_decimal, _validated_limits
from backend.app.core.ai.response_language import apply_response_language, response_language_instruction
from backend.app.core.customer_runtime_policy import is_service_access_error, safe_service_unavailable_message
from backend.app.modules.channels.vapi import build_voice_behavior_prompt


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


def test_commercial_access_errors_are_distinguished_from_provider_failures():
    assert is_service_access_error(
        HTTPException(403, {"message": "Monthly service limit reached", "service": "ai_agents"})
    )
    assert is_service_access_error(
        HTTPException(403, "Active ai_agents service subscription required")
    )
    assert not is_service_access_error(HTTPException(502, "AI provider request failed"))


def test_voice_behavior_cannot_override_employee_language_or_dialect():
    prompt = build_voice_behavior_prompt({"language": "ar", "dialect": "gulf"})
    assert "controlled by the AI Employee profile" in prompt
    assert "NEVER use this to override" in prompt


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
    assert "openWorkspaceCreateServicePlan" in source
    assert "openWorkspaceEditServicePlan" in source


def test_ai_package_editor_exposes_all_enforced_limit_dimensions():
    source = open("frontend/admin/billing-plan-management.js", encoding="utf-8").read()
    assert "['agents', 'Active AI Employees']" in source
    assert "['channels', 'Active Channels']" in source
    assert "['tokens', 'AI tokens / month']" in source
    assert "['requests', 'AI requests / month']" in source


def test_channel_capacity_is_consumed_on_activation_not_disabled_creation():
    source = open("backend/app/api/admin_channels.py", encoding="utf-8").read()
    creation_block = source.split('@router.post("/agents/{agent_id}")', 1)[1].split('@router.get("/companies/{company_id}")', 1)[0]
    activation_block = source.split('@router.put("/{channel_id}")', 1)[1].split('@router.put("/{channel_id}/whatsapp-config")', 1)[0]
    assert "check_channel_limit" not in creation_block
    assert "limits_service.check_channel_limit" in activation_block


def test_ai_employee_capacity_is_consumed_on_go_live_not_draft_creation():
    admin_source = open("backend/app/api/admin_ai_employee_profile.py", encoding="utf-8").read()
    delivery_source = open("backend/app/api/admin_delivery_readiness.py", encoding="utf-8").read()
    customer_source = open("backend/app/api/customer_agents.py", encoding="utf-8").read()
    creation_block = admin_source.split('@router.post("/companies/{company_id}")', 1)[1].split('@router.get("/companies/{company_id}/{agent_id}")', 1)[0]
    assert "limits_service.check_agent_limit" not in creation_block
    assert "enabled=False" in creation_block
    assert "limits_service.check_agent_limit(db, company_id)" in delivery_source
    assert "limits_service.check_agent_limit(db, current_user.company_id)" in customer_source
    assert "Depends(require_customer_user)" in customer_source


def test_whatsapp_and_voice_have_customer_safe_service_limit_fallbacks():
    whatsapp = open("backend/app/api/whatsapp_webhook.py", encoding="utf-8").read()
    voice = open("backend/app/api/voice_llm.py", encoding="utf-8").read()
    assert "whatsapp.customer_service_fallback" in whatsapp
    assert "is_service_access_error" in whatsapp
    assert "_voice_service_fallback" in voice
    assert "safe_service_unavailable_message" in voice
