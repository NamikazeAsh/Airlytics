import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import DailyMetric


class MetricsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_daily(self, date: datetime.date, provider: str, **fields) -> None:
        stmt = insert(DailyMetric).values(date=date, provider=provider, **fields)
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyMetric.date, DailyMetric.provider],
            set_={key: stmt.excluded[key] for key in fields},
        )
        await self.session.execute(stmt)
        await self.session.commit()
        self.session.expire_all()

    async def get_daily_range(
        self, provider: str, start: datetime.date, end: datetime.date
    ) -> list[DailyMetric]:
        stmt = (
            select(DailyMetric)
            .where(DailyMetric.provider == provider)
            .where(DailyMetric.date >= start)
            .where(DailyMetric.date <= end)
            .order_by(DailyMetric.date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
