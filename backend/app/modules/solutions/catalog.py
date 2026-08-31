SERVICE_CATALOG = {
    "ai_agents": {
        "name": "AI Agents",
        "description": "Customer service, sales, booking and order AI employees across business channels.",
        "delivery_mode": "builder",
    },
    "automation": {
        "name": "Business Automation",
        "description": "Event, schedule and webhook driven business workflows and AI-assisted operations.",
        "delivery_mode": "builder",
    },
    "analytics": {
        "name": "Data & AI Analytics",
        "description": "Connected business data sources, dashboards, analysis and recommendations.",
        "delivery_mode": "builder",
    },
    "integrations": {
        "name": "AI Integrations",
        "description": "Secure connections to POS, CRM, ERP, calendars, APIs and business systems.",
        "delivery_mode": "builder",
    },
}

AI_EMPLOYEE_CAPABILITIES = {
    "customer_service": "Answer customer questions",
    "lead_capture": "Capture and qualify leads",
    "booking": "Create and manage bookings",
    "orders": "Create and track orders",
    "sales": "Assist sales conversations",
    "human_handoff": "Transfer to a human",
}

AI_EMPLOYEE_CHANNELS = {
    "whatsapp": "WhatsApp",
    "voice": "Voice calls",
    "website": "Website chat",
}

PACKAGE_TIERS = {
    "starter": "Starter",
    "business": "Business",
    "enterprise": "Enterprise",
}

# Commercial model-power ceiling used when an AI Agents plan does not provide
# an explicit max_quality_tier override. Starter still reaches Tier 2 so core
# business actions such as bookings/orders remain fully usable. Business unlocks
# advanced reasoning; Enterprise unlocks the strongest premium tier.
AI_AGENT_PACKAGE_QUALITY_CAPS = {
    "starter": 2,
    "business": 3,
    "enterprise": 4,
}


def public_catalog() -> dict:
    return {
        "services": [
            {"code": code, **item}
            for code, item in SERVICE_CATALOG.items()
        ],
        "ai_employee_capabilities": [
            {"code": code, "name": name}
            for code, name in AI_EMPLOYEE_CAPABILITIES.items()
        ],
        "ai_employee_channels": [
            {"code": code, "name": name}
            for code, name in AI_EMPLOYEE_CHANNELS.items()
        ],
        "package_tiers": [
            {
                "code": code,
                "name": name,
                "max_quality_tier": AI_AGENT_PACKAGE_QUALITY_CAPS.get(code),
            }
            for code, name in PACKAGE_TIERS.items()
        ],
    }
