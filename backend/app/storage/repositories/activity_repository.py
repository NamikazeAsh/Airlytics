import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import ActivityLog


class ActivityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        external_activity_id: str,
        provider: str,
        date: datetime.date,
        activity_type: str,
        start_time: datetime.datetime,
        duration_minutes: int | None = None,
        calories: int | None = None,
        avg_heart_rate: int | None = None,
        distance_km: float | None = None,
    ) -> None:
        stmt = insert(ActivityLog).values(
            external_activity_id=external_activity_id,
            provider=provider,
            date=date,
            activity_type=activity_type,
            start_time=start_time,
            duration_minutes=duration_minutes,
            calories=calories,
            avg_heart_rate=avg_heart_rate,
            distance_km=distance_km,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ActivityLog.external_activity_id],
            set_={
                "date": stmt.excluded.date,
                "activity_type": stmt.excluded.activity_type,
                "start_time": stmt.excluded.start_time,
                "duration_minutes": stmt.excluded.duration_minutes,
                "calories": stmt.excluded.calories,
                "avg_heart_rate": stmt.excluded.avg_heart_rate,
                "distance_km": stmt.excluded.distance_km,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        self.session.expire_all()

    async def get_range(self, provider: str, start: datetime.date, end: datetime.date) -> list[ActivityLog]:
        stmt = (
            select(ActivityLog)
            .where(ActivityLog.provider == provider)
            .where(ActivityLog.date >= start)
            .where(ActivityLog.date <= end)
            .order_by(ActivityLog.start_time)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
