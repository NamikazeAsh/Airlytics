import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_coach.context_builder import build_system_prompt
from app.ai_coach.llm_client import Message, ToolCall
from app.ai_coach.provider_factory import get_llm_client
from app.ai_coach.tools import TOOL_SPECS, execute_tool
from app.storage.models import AiMessage
from app.storage.repositories.conversation_repository import ConversationRepository

MAX_TOOL_ROUNDS = 5
INCOMPLETE_REPLY = "I wasn't able to finish analyzing that in time — try asking a narrower question."


def _to_llm_message(m: AiMessage) -> Message:
    tool_calls = [ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"]) for tc in (m.tool_calls or [])]
    return Message(role=m.role, content=m.content, tool_calls=tool_calls, tool_call_id=m.tool_call_id)


async def send_message(session: AsyncSession, conversation_id: str | None, user_message: str) -> dict:
    repo = ConversationRepository(session)

    if conversation_id is None:
        conversation_id = str(uuid.uuid4())
        await repo.create_conversation(conversation_id)
    elif await repo.get_conversation(conversation_id) is None:
        raise ValueError(f"Unknown conversation_id '{conversation_id}'")

    await repo.add_message(conversation_id, role="user", content=user_message)

    messages = [_to_llm_message(m) for m in await repo.get_messages(conversation_id)]
    system = await build_system_prompt(session)
    llm = get_llm_client()
    tool_calls_used: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = await llm.generate(system=system, messages=messages, tools=TOOL_SPECS)

        if not response.tool_calls:
            await repo.add_message(conversation_id, role="assistant", content=response.content)
            return {"conversation_id": conversation_id, "reply": response.content, "tool_calls_used": tool_calls_used}

        wire_tool_calls = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
        await repo.add_message(
            conversation_id, role="assistant", content=response.content, tool_calls=wire_tool_calls
        )
        messages.append(Message(role="assistant", content=response.content, tool_calls=response.tool_calls))

        for tc in response.tool_calls:
            result = json.dumps(await execute_tool(session, tc.name, tc.arguments))
            tool_calls_used.append(tc.name)
            await repo.add_message(conversation_id, role="tool", content=result, tool_call_id=tc.id)
            messages.append(Message(role="tool", content=result, tool_call_id=tc.id))

    await repo.add_message(conversation_id, role="assistant", content=INCOMPLETE_REPLY)
    return {"conversation_id": conversation_id, "reply": INCOMPLETE_REPLY, "tool_calls_used": tool_calls_used}
