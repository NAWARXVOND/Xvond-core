COMMON_TEXT_BEHAVIOR_FIELDS = [
    {
        "name": "language",
        "label": "Response Language",
        "required": False,
        "secret": False,
        "default": "auto",
    },
    {
        "name": "dialect",
        "label": "Dialect",
        "required": False,
        "secret": False,
        "default": "auto",
    },
    {
        "name": "tone",
        "label": "Tone",
        "required": False,
        "secret": False,
        "default": "professional_friendly",
    },
    {
        "name": "response_style",
        "label": "Response Style",
        "required": False,
        "secret": False,
        "default": "natural",
    },
    {
        "name": "response_length",
        "label": "Response Length",
        "required": False,
        "secret": False,
        "default": "concise",
    },
    {
        "name": "channel_instructions",
        "label": "Channel-specific Instructions",
        "required": False,
        "secret": False,
    },
]


CHANNEL_CATALOG = {

    "whatsapp": {
        "name": "WhatsApp",
        "description": "WhatsApp Business Cloud API",
        "config_fields": [
            {
                "name": "phone_number_id",
                "label": "Phone Number ID",
                "required": True,
                "secret": False,
            },
            {
                "name": "access_token",
                "label": "Access Token",
                "required": True,
                "secret": True,
            },
            {
                "name": "verify_token",
                "label": "Verify Token",
                "required": True,
                "secret": True,
            },
            {
                "name": "app_secret",
                "label": "App Secret",
                "required": True,
                "secret": True,
            },
            {
                "name": "graph_api_version",
                "label": "Graph API Version",
                "required": True,
                "secret": False,
                "default": "v23.0",
            },
            *COMMON_TEXT_BEHAVIOR_FIELDS,
            {
                "name": "emoji_style",
                "label": "Emoji Style",
                "required": False,
                "secret": False,
                "default": "minimal",
            },
            {
                "name": "greeting_message",
                "label": "WhatsApp Greeting",
                "required": False,
                "secret": False,
            },
        ],
    },

    "website": {
        "name": "Website Chat",
        "description": "AI chat widget for customer websites",
        "config_fields": [
            {
                "name": "allowed_domain",
                "label": "Allowed Domain",
                "required": True,
                "secret": False,
            },
            {
                "name": "widget_name",
                "label": "Widget Name",
                "required": False,
                "secret": False,
            },
            *COMMON_TEXT_BEHAVIOR_FIELDS,
            {
                "name": "greeting_message",
                "label": "Website Greeting",
                "required": False,
                "secret": False,
            },
        ],
    },

    "voice": {
        "name": "Voice",
        "description": "AI voice channel",
        "config_fields": [
            {
                "name": "provider",
                "label": "Voice Provider",
                "required": True,
                "secret": False,
            },
            {
                "name": "phone_number",
                "label": "Phone Number",
                "required": True,
                "secret": False,
            },
            {
                "name": "account_id",
                "label": "Account ID",
                "required": False,
                "secret": False,
            },
            {
                "name": "auth_token",
                "label": "Auth Token",
                "required": False,
                "secret": True,
            },
            {
                "name": "language",
                "label": "Spoken Language",
                "required": False,
                "secret": False,
                "default": "auto",
            },
            {
                "name": "dialect",
                "label": "Spoken Dialect",
                "required": False,
                "secret": False,
                "default": "auto",
            },
            {
                "name": "tone",
                "label": "Speaking Tone",
                "required": False,
                "secret": False,
                "default": "professional_friendly",
            },
            {
                "name": "voice_id",
                "label": "Voice ID",
                "required": False,
                "secret": False,
            },
            {
                "name": "voice_gender",
                "label": "Voice Gender",
                "required": False,
                "secret": False,
                "default": "provider_default",
            },
            {
                "name": "speaking_rate",
                "label": "Speaking Rate",
                "required": False,
                "secret": False,
                "default": "normal",
            },
            {
                "name": "allow_interruption",
                "label": "Allow Caller Interruption",
                "required": False,
                "secret": False,
                "default": True,
            },
            {
                "name": "response_length",
                "label": "Spoken Response Length",
                "required": False,
                "secret": False,
                "default": "short",
            },
            {
                "name": "greeting_message",
                "label": "Call Greeting",
                "required": False,
                "secret": False,
            },
            {
                "name": "closing_message",
                "label": "Call Closing",
                "required": False,
                "secret": False,
            },
            {
                "name": "silence_timeout_seconds",
                "label": "Silence Timeout Seconds",
                "required": False,
                "secret": False,
                "default": 8,
            },
            {
                "name": "channel_instructions",
                "label": "Voice-specific Instructions",
                "required": False,
                "secret": False,
            },
        ],
    },

    "telegram": {
        "name": "Telegram",
        "description": "Telegram Bot channel",
        "config_fields": [
            {
                "name": "bot_token",
                "label": "Bot Token",
                "required": True,
                "secret": True,
            },
            *COMMON_TEXT_BEHAVIOR_FIELDS,
        ],
    },

    "custom": {
        "name": "Custom Channel",
        "description": "Custom customer communication channel",
        "config_fields": [
            {
                "name": "endpoint",
                "label": "Endpoint",
                "required": True,
                "secret": False,
            },
            {
                "name": "api_key",
                "label": "API Key",
                "required": False,
                "secret": True,
            },
            *COMMON_TEXT_BEHAVIOR_FIELDS,
        ],
    },
}


def get_channel_definition(channel_type: str):
    return CHANNEL_CATALOG.get(channel_type)


def list_channel_definitions():
    return [
        {
            "type": key,
            **value,
        }
        for key, value in CHANNEL_CATALOG.items()
    ]


def validate_channel_config(
    channel_type: str,
    config: dict,
):
    definition = get_channel_definition(
        channel_type
    )

    if definition is None:
        raise ValueError(
            f"Unsupported channel type: {channel_type}"
        )

    missing = []

    for field in definition["config_fields"]:

        if not field.get("required"):
            continue

        name = field["name"]

        value = config.get(
            name,
            field.get("default"),
        )

        if value is None or str(value).strip() == "":
            missing.append(name)

    if missing:
        raise ValueError(
            "Missing channel configuration: "
            + ", ".join(missing)
        )

    return True
