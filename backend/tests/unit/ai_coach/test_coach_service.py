import pytest

from app.ai_coach import coach_service
from app.ai_coach.llm_client import LLMResponse, ToolCall
from app.storage.repositories.conversation_repository import ConversationRepository


class FakeLLMClient:
    """A minimal stand-in LLMClient. Its only job is to prove coach_service
    works against *any* implementation of the Protocol, unmodified — which is
    the actual claim "the LLM provider is swappable" needs to demonstrate."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = iter(responses)
        self.calls = []

    async def generate(self, *, system, messages, tools=None):
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        return next(self._responses)


async def _fake_execute_tool(session, name, arguments):
    return {"average": 8000}


async def test_send_message_new_conversation_simple_reply(db_session, monkeypatch):
    fake = FakeLLMClient([LLMResponse(content="Your steps are trending up.", tool_calls=[])])
    monkeypatch.setattr(coach_service, "get_llm_client", lambda: fake)

    result = await coach_service.send_message(db_session, None, "How are my steps?")

    assert result["reply"] == "Your steps are trending up."
    assert result["tool_calls_used"] == []
    assert result["conversation_id"]

    messages = await ConversationRepository(db_session).get_messages(result["conversation_id"])
    assert [m.role for m in messages] == ["user", "assistant"]


async def test_send_message_executes_tool_call_then_answers(db_session, monkeypatch):
    fake = FakeLLMClient(
        [
            LLMResponse(content=None, tool_calls=[ToolCall(id="call_1", name="get_rolling_average", arguments={})]),
            LLMResponse(content="Based on that, you're averaging well.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr(coach_service, "get_llm_client", lambda: fake)
    monkeypatch.setattr(coach_service, "execute_tool", _fake_execute_tool)

    result = await coach_service.send_message(db_session, None, "How am I doing?")

    assert result["reply"] == "Based on that, you're averaging well."
    assert result["tool_calls_used"] == ["get_rolling_average"]

    messages = await ConversationRepository(db_session).get_messages(result["conversation_id"])
    assert [m.role for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert messages[1].tool_calls == [{"id": "call_1", "name": "get_rolling_average", "arguments": {}}]
    assert messages[2].tool_call_id == "call_1"


async def test_send_message_gives_up_after_max_rounds(db_session, monkeypatch):
    always_calls_tool = LLMResponse(
        content=None, tool_calls=[ToolCall(id="call_1", name="get_rolling_average", arguments={})]
    )
    fake = FakeLLMClient([always_calls_tool] * coach_service.MAX_TOOL_ROUNDS)
    monkeypatch.setattr(coach_service, "get_llm_client", lambda: fake)
    monkeypatch.setattr(coach_service, "execute_tool", _fake_execute_tool)

    result = await coach_service.send_message(db_session, None, "How am I doing?")

    assert result["reply"] == coach_service.INCOMPLETE_REPLY


async def test_send_message_continues_existing_conversation(db_session, monkeypatch):
    fake = FakeLLMClient([LLMResponse(content="first reply", tool_calls=[])])
    monkeypatch.setattr(coach_service, "get_llm_client", lambda: fake)
    first = await coach_service.send_message(db_session, None, "hello")
    conversation_id = first["conversation_id"]

    fake2 = FakeLLMClient([LLMResponse(content="second reply", tool_calls=[])])
    monkeypatch.setattr(coach_service, "get_llm_client", lambda: fake2)
    second = await coach_service.send_message(db_session, conversation_id, "follow up")

    assert second["conversation_id"] == conversation_id
    assert len(fake2.calls[0]["messages"]) == 3  # first user + first assistant + new user


async def test_send_message_unknown_conversation_id_raises(db_session, monkeypatch):
    fake = FakeLLMClient([LLMResponse(content="reply", tool_calls=[])])
    monkeypatch.setattr(coach_service, "get_llm_client", lambda: fake)

    with pytest.raises(ValueError):
        await coach_service.send_message(db_session, "does-not-exist", "hi")
