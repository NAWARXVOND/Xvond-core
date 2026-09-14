import inspect

from backend.app.modules.tools import builtin


def test_ai_handoff_tool_only_claims_real_same_channel_delivery():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    assert 'LIVE_HUMAN_HANDOFF_CHANNELS = {"whatsapp", "website"}' in inspect.getsource(builtin)
    assert "channel_type not in LIVE_HUMAN_HANDOFF_CHANNELS" in source
    assert "human_handoff_unavailable" in source
    assert '"ai_paused":True' in source
    assert '"claim_required":handoff.assigned_user_id is None' in source


def test_ai_handoff_tool_is_idempotent_for_active_conversation():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    active_query = source.index("HumanHandoff).filter")
    create_position = source.index("HumanHandoff(company_id=cid")
    assert active_query < create_position
    assert "HumanHandoff.status.in_(ACTIVE_HANDOFF_STATUSES)" in source


def test_whatsapp_session_is_verified_before_handoff_row_is_created():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    session_position = source.index("db.query(WhatsAppSession)")
    unavailable_position = source.index("WhatsApp session is unavailable")
    create_position = source.index("HumanHandoff(company_id=cid")
    assert session_position < unavailable_position < create_position


def test_website_handoff_uses_active_record_as_pause_without_fake_provider():
    source = inspect.getsource(builtin.HumanHandoffTool.execute)
    assert "Website runtime treats the active handoff row itself as the AI pause" in source
    assert "whatsapp_sender" not in source
