SERVICE_CATALOG = {
    "ai_agents": {
        "name": "AI Employees & Agents",
        "description": "Customer service, sales, booking, order, website, WhatsApp and voice AI employees.",
        "delivery_mode": "monthly",
        "builder": True,
    },
    "automation": {
        "name": "Business Automation",
        "description": "Reusable event-driven workflows and AI-assisted business operations.",
        "delivery_mode": "monthly",
        "builder": True,
    },
    "analytics": {
        "name": "Data & AI Analytics",
        "description": "Connected business data, dashboards, analysis and AI recommendations.",
        "delivery_mode": "monthly",
        "builder": True,
    },
    "integrations": {
        "name": "AI Integrations",
        "description": "Secure connections to CRM, ERP, POS, booking systems, APIs and databases.",
        "delivery_mode": "monthly",
        "builder": True,
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
            {"code": code, "name": name}
            for code, name in PACKAGE_TIERS.items()
        ],
    }
