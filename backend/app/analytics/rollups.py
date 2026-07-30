import datetime

import numpy as np
from scipy.stats import linregress
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import METRICS, AnalyticsService
from app.storage.repositories.period_summary_repository import PeriodSummaryRepository

WEEKLY_PERIODS_TO_COMPUTE = 12
MONTHLY_PERIODS_TO_COMPUTE = 12


def _week_start(date: datetime.date) -> datetime.date:
    return date - datetime.timedelta(days=date.weekday())


def _month_start(date: datetime.date) -> datetime.date:
    return date.replace(day=1)


def _add_months(date: datetime.date, months: int) -> datetime.date:
    month_index = date.month - 1 + months
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    return date.replace(year=year, month=month, day=1)


def _slope_per_day(series) -> float | None:
    if len(series) < 2:
        return None
    x = np.array([(d - series.index.min()).days for d in series.index], dtype=float)
    if x.max() == 0:
        return None
    return round(float(linregress(x, series.values).slope), 4)


async def compute_rollups(session: AsyncSession, provider: str, as_of: datetime.date | None = None) -> None:
    as_of = as_of or datetime.date.today()
    analytics = AnalyticsService(session)
    repo = PeriodSummaryRepository(session)

    current_week_start = _week_start(as_of)
    for i in range(WEEKLY_PERIODS_TO_COMPUTE):
        period_start = current_week_start - datetime.timedelta(weeks=i)
        period_end = period_start + datetime.timedelta(days=6)
        await _compute_period(analytics, repo, provider, "weekly", period_start, period_end)

    current_month_start = _month_start(as_of)
    for i in range(MONTHLY_PERIODS_TO_COMPUTE):
        period_start = _add_months(current_month_start, -i)
        period_end = _add_months(period_start, 1) - datetime.timedelta(days=1)
        await _compute_period(analytics, repo, provider, "monthly", period_start, period_end)


async def _compute_period(
    analytics: AnalyticsService,
    repo: PeriodSummaryRepository,
    provider: str,
    period_type: str,
    period_start: datetime.date,
    period_end: datetime.date,
) -> None:
    df = await analytics._dataframe(provider, period_start, period_end)

    for metric in METRICS:
        series = df[metric].dropna() if not df.empty and metric in df else None

        if series is None or series.empty:
            await repo.upsert(
                period_start=period_start,
                period_type=period_type,
                metric=metric,
                provider=provider,
                avg_value=None,
                min_value=None,
                max_value=None,
                stddev_value=None,
                trend_slope=None,
                sample_count=0,
            )
            continue

        await repo.upsert(
            period_start=period_start,
            period_type=period_type,
            metric=metric,
            provider=provider,
            avg_value=round(float(series.mean()), 2),
            min_value=round(float(series.min()), 2),
            max_value=round(float(series.max()), 2),
            stddev_value=round(float(series.std()), 2) if len(series) > 1 else 0.0,
            trend_slope=_slope_per_day(series),
            sample_count=len(series),
        )
