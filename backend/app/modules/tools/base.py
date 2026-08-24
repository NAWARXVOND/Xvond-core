from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None


class AgentTool(ABC):
    name: str = ""
    description: str = ""

    input_schema: dict = {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }

    @abstractmethod
    def execute(
        self,
        arguments: dict,
        context: dict,
    ) -> ToolResult:
        pass
