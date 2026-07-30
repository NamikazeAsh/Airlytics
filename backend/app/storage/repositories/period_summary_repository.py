import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import PeriodSummary


class PeriodSummaryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        period_start: datetime.date,
        period_type: str,
        metric: str,
        provider: str,
        avg_value: float | None,
        min_value: float | None,
        max_value: float | None,
        stddev_value: float | None,
        trend_slope: float | None,
        sample_count: int,
    ) -> None:
        stmt = insert(PeriodSummary).values(
            period_start=period_start,
            period_type=period_type,
            metric=metric,
            provider=provider,
            avg_value=avg_value,
            min_value=min_value,
            max_value=max_value,
            stddev_value=stddev_value,
            trend_slope=trend_slope,
            sample_count=sample_count,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PeriodSummary.period_start, PeriodSummary.period_type, PeriodSummary.metric],
            set_={
                "avg_value": stmt.excluded.avg_value,
                "min_value": stmt.excluded.min_value,
                "max_value": stmt.excluded.max_value,
                "stddev_value": stmt.excluded.stddev_value,
                "trend_slope": stmt.excluded.trend_slope,
                "sample_count": stmt.excluded.sample_count,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        self.session.expire_all()

    async def get_range(
        self, provider: str, period_type: str, metric: str, start: datetime.date, end: datetime.date
    ) -> list[PeriodSummary]:
        stmt = (
            select(PeriodSummary)
            .where(PeriodSummary.provider == provider)
            .where(PeriodSummary.period_type == period_type)
            .where(PeriodSummary.metric == metric)
            .where(PeriodSummary.period_start >= start)
            .where(PeriodSummary.period_start <= end)
            .order_by(PeriodSummary.period_start)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
