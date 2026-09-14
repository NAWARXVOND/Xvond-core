from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_runtime_passes_current_message_into_quality_routing():
    code = source("backend/app/core/agent_runtime.py")
    assert "message=message" in code
    assert "runtime_selections(" in code


def test_informational_turns_can_skip_tool_schema_overhead():
    code = source("backend/app/core/agent_runtime.py")
    assert "_message_may_need_tools(message, history)" in code
    assert "tools_relevant" in code
    assert '"tool_schemas_sent": len(tool_definitions)' in code


def test_runtime_records_component_and_end_to_end_latency():
    code = source("backend/app/core/agent_runtime.py")
    for marker in (
        'stage_timings_ms["access_and_limits"]',
        'stage_timings_ms["routing"]',
        'stage_timings_ms["conversation_context"]',
        'stage_timings_ms["knowledge"]',
        'stage_timings_ms["tool_discovery"]',
        'stage_timings_ms["model"]',
        'stage_timings_ms["tool_execution"]',
        '"end_to_end_latency_ms": end_to_end_latency_ms',
        '"latency_ms": attempt_ms',
        '"latency_ms": tool_latency_ms',
    ):
        assert marker in code


def test_tool_intent_detector_keeps_action_continuations_enabled():
    from backend.app.core.agent_runtime import _message_may_need_tools

    assert _message_may_need_tools("مرحبا") is False
    assert _message_may_need_tools("شو خدماتكم؟") is False
    assert _message_may_need_tools("بدي احجز موعد") is True
    assert _message_may_need_tools("تمام", "assistant: شو الوقت المناسب للحجز؟") is True
    assert _message_may_need_tools("yes", "assistant: please confirm your order") is True
