from backend.app.api.admin_agent_actions import TEMPLATES
from backend.app.modules.tools.action_request import _customer_confirmed, _field_specs, _missing


def test_arabic_and_english_customer_confirmation():
    assert _customer_confirmed("تمام") is True
    assert _customer_confirmed("نعم أكد الطلب") is True
    assert _customer_confirmed("yes") is True
    assert _customer_confirmed("لا، غير الطلب") is False
    assert _customer_confirmed("no") is False


def test_structured_fields_preserve_optional_rules():
    action = {
        "fields": [
            {"key": "customer_name", "label": "Customer name", "required": True, "type": "text"},
            {"key": "notes", "label": "Notes", "required": False, "type": "text"},
        ]
    }
    specs = _field_specs(action)
    assert specs[0]["required"] is True
    assert specs[1]["required"] is False
    assert _missing(action, {"customer_name": "Nawar"}) == []


def test_enabled_template_operations_have_real_destinations():
    for template in TEMPLATES:
        keys = set()
        for action in template["actions"]:
            assert action["key"] not in keys
            keys.add(action["key"])
            if action.get("enabled", True):
                assert (action.get("destination") or {}).get("type") in {
                    "xvond_internal",
                    "human_handoff",
                    "integration",
                }


def test_catering_template_is_real_internal_intake_by_default():
    template = next(x for x in TEMPLATES if x["id"] == "catering")
    request = next(x for x in template["actions"] if x["key"] == "catering_request")
    assert request["enabled"] is True
    assert request["destination"]["type"] == "xvond_internal"
    required = {x["key"] for x in request["fields"] if x.get("required", True)}
    assert {"customer_name", "phone", "event_type", "event_date", "guest_count", "location", "request"} <= required
