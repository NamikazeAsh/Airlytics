import json

import respx
from httpx import Response

from app.ai_coach.llm_client import Message, ToolCall, ToolSpec
from app.ai_coach.providers.groq_client import BASE_URL, GroqClient


@respx.mock
async def test_generate_returns_text_response():
    respx.post(BASE_URL).mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "Your steps are up 10%."}}]},
        )
    )

    client = GroqClient(api_key="test-key", model="openai/gpt-oss-120b")
    response = await client.generate(system="You are a coach.", messages=[Message(role="user", content="Hi")])

    assert response.content == "Your steps are up 10%."
    assert response.tool_calls == []


@respx.mock
async def test_generate_parses_tool_calls():
    respx.post(BASE_URL).mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "get_trend", "arguments": '{"metric": "steps_total"}'},
                                }
                            ],
                        }
                    }
                ]
            },
        )
    )

    client = GroqClient(api_key="test-key", model="openai/gpt-oss-120b")
    response = await client.generate(
        system="sys",
        messages=[Message(role="user", content="How are my steps trending?")],
        tools=[ToolSpec(name="get_trend", description="d", parameters={"type": "object", "properties": {}})],
    )

    assert response.content is None
    assert response.tool_calls == [ToolCall(id="call_1", name="get_trend", arguments={"metric": "steps_total"})]


@respx.mock
async def test_generate_sends_tool_result_message_correctly():
    route = respx.post(BASE_URL).mock(
        return_value=Response(200, json={"choices": [{"message": {"role": "assistant", "content": "done"}}]})
    )

    client = GroqClient(api_key="test-key", model="openai/gpt-oss-120b")
    await client.generate(
        system="sys",
        messages=[
            Message(role="assistant", tool_calls=[ToolCall(id="call_1", name="get_trend", arguments={"a": 1})]),
            Message(role="tool", content='{"direction": "up"}', tool_call_id="call_1"),
        ],
    )

    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body["messages"][1]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'
    assert sent_body["messages"][2]["role"] == "tool"
    assert sent_body["messages"][2]["tool_call_id"] == "call_1"
