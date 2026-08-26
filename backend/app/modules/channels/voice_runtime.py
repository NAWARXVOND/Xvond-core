from __future__ import annotations

from backend.app.core.agent_runtime import AgentRuntime
from backend.app.core.config_secrets import reveal_config
from backend.app.modules.channels.behavior import build_channel_behavior_prompt
from backend.app.modules.channels.models import AgentChannel


class VoiceAgentRuntime(AgentRuntime):
    """Run a voice turn through the same Xvond agent core used by text channels."""

    def __init__(self, channel_config: dict | None = None):
        super().__init__()
        self.channel_config = channel_config or {}

    def resolve_channel_behavior(
        self,
        db,
        company_id: int,
        agent_id: int,
        conversation_id: int,
    ) -> tuple[str | None, str]:
        return (
            "voice",
            build_channel_behavior_prompt(
                "voice",
                self.channel_config,
            ),
        )


def get_voice_channel(db, channel_id: int) -> AgentChannel:
    channel = (
        db.query(AgentChannel)
        .filter(
            AgentChannel.id == channel_id,
            AgentChannel.channel_type == "voice",
            AgentChannel.enabled.is_(True),
        )
        .first()
    )

    if channel is None:
        raise ValueError("Enabled voice channel not found")

    return channel


def run_voice_turn(
    db,
    channel: AgentChannel,
    transcript: str,
    conversation_id: int | None = None,
) -> dict:
    config = reveal_config(channel.config)
    runtime = VoiceAgentRuntime(config)

    return runtime.chat(
        db=db,
        company_id=channel.company_id,
        agent_id=channel.agent_id,
        message=transcript,
        conversation_id=conversation_id,
    )
