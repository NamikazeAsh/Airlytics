from app.storage.repositories.conversation_repository import ConversationRepository


async def test_create_and_get_conversation(db_session):
    repo = ConversationRepository(db_session)
    await repo.create_conversation("conv-1")

    conversation = await repo.get_conversation("conv-1")
    assert conversation is not None
    assert conversation.id == "conv-1"


async def test_get_conversation_missing_returns_none(db_session):
    repo = ConversationRepository(db_session)
    assert await repo.get_conversation("does-not-exist") is None


async def test_add_and_get_messages_in_order(db_session):
    repo = ConversationRepository(db_session)
    await repo.create_conversation("conv-1")
    await repo.add_message("conv-1", role="user", content="hi")
    await repo.add_message(
        "conv-1", role="assistant", tool_calls=[{"id": "call_1", "name": "get_trend", "arguments": {}}]
    )
    await repo.add_message("conv-1", role="tool", content='{"ok": true}', tool_call_id="call_1")

    messages = await repo.get_messages("conv-1")
    assert [m.role for m in messages] == ["user", "assistant", "tool"]
    assert messages[1].tool_calls == [{"id": "call_1", "name": "get_trend", "arguments": {}}]
    assert messages[2].tool_call_id == "call_1"
