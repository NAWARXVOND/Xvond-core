def can_view_conversations(config) -> bool:
    """Return whether customer managers may view an AI employee's conversations.

    Profile-based AI employees do not necessarily have an AgentConfig row. For
    those employees, conversation visibility defaults to enabled. If an
    AgentConfig exists, its explicit customer control remains authoritative.
    """
    if config is None:
        return True
    controls = config.customer_controls or {}
    return bool(controls.get("can_view_conversations", False))
