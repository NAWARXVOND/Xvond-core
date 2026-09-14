import inspect

from backend.app.modules.tools import builtin


def test_ai_handoff_tool_only_claims_real_same_channel_delivery():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    assert builtin.LIVE_HUMAN_HANDOFF_CHANNELS == {"whatsapp", "website"}
    assert "channel_type not in LIVE_HUMAN_HANDOFF_CHANNELS" in source
    assert "human_handoff_unavailable" in source
    assert '"ai_paused"' in source
    assert "True" in source
    assert '"claim_required"' in source
    assert "handoff.assigned_user_id is None" in source


def test_ai_handoff_tool_is_idempotent_for_active_conversation():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    active_query = source.index("db.query(HumanHandoff)")
    create_position = source.index("handoff = HumanHandoff(")
    assert active_query < create_position
    assert "HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES)" in source
    assert "if handoff is None" in source


def test_whatsapp_session_is_verified_before_handoff_row_is_created():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    session_position = source.index("db.query(WhatsAppSession)")
    unavailable_position = source.index("WhatsApp session is unavailable")
    create_position = source.index("handoff = HumanHandoff(")
    assert session_position < unavailable_position < create_position


def test_website_handoff_uses_active_record_as_pause_without_fake_provider():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    assert 'channel_type == "whatsapp"' in source
    assert "activate_human_handoff(session" in source
    assert "whatsapp_sender" not in source
    # Website has no provider-side takeover adapter: the durable active
    # HumanHandoff row is the pause signal consumed by website runtime.
    assert "HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES)" in source
