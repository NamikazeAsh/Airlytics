import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import AiInsight


class InsightRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, category: str, body: str) -> None:
        self.session.add(AiInsight(category=category, body=body))
        await self.session.commit()

    async def get_since(self, since: datetime.datetime) -> list[AiInsight]:
        stmt = (
            select(AiInsight)
            .where(AiInsight.generated_at >= since)
            .order_by(AiInsight.generated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
