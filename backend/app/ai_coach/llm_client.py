from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema for the tool's arguments


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # set on role="tool" messages, echoing the call being answered


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]


class LLMClient(Protocol):
    async def generate(
        self, *, system: str, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse: ...
