from backend.app.modules.channels.voice_runtime import VoiceAgentRuntime


def test_voice_runtime_forces_voice_channel_behavior():
    runtime = VoiceAgentRuntime(
        {
            "language": "ar",
            "dialect": "omani",
            "tone": "friendly",
            "response_length": "short",
        }
    )

    channel_type, prompt = runtime.resolve_channel_behavior(
        db=None,
        company_id=1,
        agent_id=2,
        conversation_id=3,
    )

    assert channel_type == "voice"
    assert "RESPONSE LANGUAGE: ar" in prompt
    assert "DIALECT: omani" in prompt
    assert "TONE: friendly" in prompt
    assert "Write responses for speech" in prompt
