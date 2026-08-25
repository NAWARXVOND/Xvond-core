SERVICE_CATALOG = {
    "strategy": {
        "name": "AI Strategy & Consulting",
        "description": "Assessment, use-case discovery, roadmap, and implementation planning.",
        "delivery_mode": "project",
    },
    "ai_agents": {
        "name": "AI Employees & Agents",
        "description": "Customer service, sales, booking, order, and specialist AI employees.",
        "delivery_mode": "provisioned",
    },
    "automation": {
        "name": "Business Automation",
        "description": "Reliable event-driven business workflows and AI-assisted operations.",
        "delivery_mode": "project",
    },
    "analytics": {
        "name": "Data & AI Analytics",
        "description": "Connected business data, analysis, dashboards, and recommendations.",
        "delivery_mode": "project",
    },
    "custom_ai": {
        "name": "Custom AI Systems",
        "description": "Purpose-built AI applications, document intelligence, and prediction systems.",
        "delivery_mode": "project",
    },
    "integrations": {
        "name": "AI Integrations",
        "description": "Secure connections to CRM, ERP, accounting, inventory, APIs, and databases.",
        "delivery_mode": "project",
    },
    "marketing": {
        "name": "AI Marketing & Production",
        "description": "Campaign strategy, text, image, video, voice, and performance analysis.",
        "delivery_mode": "project",
    },
    "support": {
        "name": "Training, Support & Continuous Improvement",
        "description": "Training, monitoring, incident handling, optimization, and ongoing development.",
        "delivery_mode": "subscription",
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
    "omnichannel": "Omnichannel",
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
