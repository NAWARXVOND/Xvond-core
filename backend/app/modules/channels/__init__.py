from backend.app.core.module import BaseModule
from backend.app.modules.channels.models import AgentChannel


class ChannelsModule(BaseModule):
    name = "channels"
    version = "1.0.0"
    description = "Xvond Agent Channels"
