import json

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.ai_coach.llm_client import LLMResponse, Message, ToolCall, ToolSpec

BASE_URL = "https://api.groq.com/openai/v1/chat/completions"


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504)


def _message_to_wire(message: Message) -> dict:
    wire: dict = {"role": message.role}
    if message.content is not None:
        wire["content"] = message.content
    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for tc in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def _tool_to_wire(tool: ToolSpec) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
    }


class GroqClient:
    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    @retry(retry=retry_if_exception(_is_retryable), stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
    async def generate(
        self, *, system: str, messages: list[Message], tools: list[ToolSpec] | None = None
    ) -> LLMResponse:
        wire_messages = [{"role": "system", "content": system}, *[_message_to_wire(m) for m in messages]]
        body: dict = {"model": self._model, "messages": wire_messages}
        if tools:
            body["tools"] = [_tool_to_wire(t) for t in tools]
            body["tool_choice"] = "auto"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                BASE_URL, json=body, headers={"Authorization": f"Bearer {self._api_key}"}, timeout=60
            )
            response.raise_for_status()

        choice = response.json()["choices"][0]["message"]
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=json.loads(tc["function"]["arguments"]))
            for tc in choice.get("tool_calls") or []
        ]
        return LLMResponse(content=choice.get("content"), tool_calls=tool_calls)
