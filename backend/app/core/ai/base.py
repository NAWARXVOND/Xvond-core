from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ToolOutput:
    call_id: str
    name: str
    success: bool
    data: Any = None
    error: str | None = None


@dataclass
class AIResponse:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: Decimal = Decimal("0")
    tool_calls: list[ToolCall] = field(default_factory=list)
    continuation: Any = None


class AIProvider(ABC):

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        tools: list[dict] | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        continuation: Any = None,
    ) -> AIResponse:
        pass
