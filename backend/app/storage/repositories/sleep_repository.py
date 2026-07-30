import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import SleepLog


class SleepRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        external_log_id: str,
        provider: str,
        date: datetime.date,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        duration_minutes: int | None = None,
        efficiency: int | None = None,
        stages: dict | None = None,
    ) -> None:
        stmt = insert(SleepLog).values(
            external_log_id=external_log_id,
            provider=provider,
            date=date,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            efficiency=efficiency,
            stages=stages,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SleepLog.external_log_id],
            set_={
                "date": stmt.excluded.date,
                "start_time": stmt.excluded.start_time,
                "end_time": stmt.excluded.end_time,
                "duration_minutes": stmt.excluded.duration_minutes,
                "efficiency": stmt.excluded.efficiency,
                "stages": stmt.excluded.stages,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        self.session.expire_all()

    async def get_range(self, provider: str, start: datetime.date, end: datetime.date) -> list[SleepLog]:
        stmt = (
            select(SleepLog)
            .where(SleepLog.provider == provider)
            .where(SleepLog.date >= start)
            .where(SleepLog.date <= end)
            .order_by(SleepLog.start_time)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
