from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import AiConversation, AiMessage


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_conversation(self, conversation_id: str) -> None:
        self.session.add(AiConversation(id=conversation_id))
        await self.session.commit()

    async def get_conversation(self, conversation_id: str) -> AiConversation | None:
        return await self.session.get(AiConversation, conversation_id)

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str | None = None,
        tool_calls: list | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        self.session.add(
            AiMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
            )
        )
        await self.session.commit()

    async def get_messages(self, conversation_id: str) -> list[AiMessage]:
        stmt = (
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
