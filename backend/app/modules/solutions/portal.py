from __future__ import annotations


BUSINESS_CAPABILITY_MODULES = {
    "booking",
    "orders",
    "quotation",
    "lead_management",
    "customer_support",
}

SERVICE_PORTAL_REGISTRY = {
    "ai_agents": {
        "group": "AI Agents",
        "items": [
            {"id": "agents", "label": "AI Employees", "loader": "agents"},
            {"id": "chat", "label": "Test AI Employee", "loader": "chat"},
            {"id": "conversations", "label": "Conversations", "loader": "conversations"},
            {"id": "usage", "label": "Usage", "loader": "usage"},
        ],
    },
    "automation": {
        "group": "Business Automation",
        "items": [
            {
                "id": "service-automation",
                "label": "Automation",
                "loader": "service",
                "service_code": "automation",
            }
        ],
    },
    "analytics": {
        "group": "Data & AI Analytics",
        "items": [
            {
                "id": "service-analytics",
                "label": "Analytics",
                "loader": "service",
                "service_code": "analytics",
            }
        ],
    },
    "integrations": {
        "group": "AI Integrations",
        "items": [
            {
                "id": "integrations",
                "label": "Connected Systems",
                "loader": "integrations",
                "service_code": "integrations",
            }
        ],
    },
}

SERVICE_ORDER = ("ai_agents", "automation", "analytics", "integrations")


def _item_with_group(item: dict, group: str, service_code: str | None = None) -> dict:
    value = {**item, "group": group}
    if service_code and not value.get("service_code"):
        value["service_code"] = service_code
    return value


def build_customer_portal_navigation(
    active_service_codes: list[str] | set[str] | tuple[str, ...],
    enabled_modules: list[str] | set[str] | tuple[str, ...],
) -> list[dict]:
    active = {str(code).strip() for code in active_service_codes if str(code).strip()}
    modules = {str(name).strip() for name in enabled_modules if str(name).strip()}

    navigation = [
        {"id": "dashboard", "label": "Overview", "loader": "dashboard", "group": "Workspace"}
    ]

    ordered_services = [code for code in SERVICE_ORDER if code in active]
    ordered_services.extend(sorted(active.difference(ordered_services)))

    for service_code in ordered_services:
        definition = SERVICE_PORTAL_REGISTRY.get(service_code)
        if definition is None:
            navigation.append(
                {
                    "id": f"service-{service_code}",
                    "label": service_code.replace("_", " ").title(),
                    "loader": "service",
                    "service_code": service_code,
                    "group": service_code.replace("_", " ").title(),
                }
            )
            continue

        group = definition["group"]
        for item in definition["items"]:
            # Business requests belong to the AI Agents service, but only make
            # sense when at least one executable business capability is enabled.
            if service_code == "ai_agents" and item["id"] == "usage":
                if modules.intersection(BUSINESS_CAPABILITY_MODULES):
                    navigation.append(
                        {
                            "id": "business",
                            "label": "Requests & Operations",
                            "loader": "business",
                            "service_code": "ai_agents",
                            "group": group,
                        }
                    )
            navigation.append(_item_with_group(item, group, service_code))

    navigation.append(
        {"id": "billing", "label": "Billing", "loader": "billing", "group": "Account"}
    )
    return navigation
