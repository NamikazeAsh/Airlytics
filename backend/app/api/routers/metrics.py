import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import METRICS
from app.auth.token_service import PROVIDER
from app.core.database import get_session
from app.storage.repositories.metrics_repository import MetricsRepository
from app.storage.repositories.sleep_repository import SleepRepository

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/daily")
async def daily(
    metric: str, start: datetime.date, end: datetime.date, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'. Valid: {METRICS}")

    rows = await MetricsRepository(session).get_daily_range(provider=PROVIDER, start=start, end=end)
    return [{"date": row.date.isoformat(), "value": getattr(row, metric)} for row in rows]


@router.get("/sleep")
async def sleep(
    start: datetime.date, end: datetime.date, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    logs = await SleepRepository(session).get_range(provider=PROVIDER, start=start, end=end)
    return [
        {
            "date": log.date.isoformat(),
            "start_time": log.start_time.isoformat(),
            "end_time": log.end_time.isoformat(),
            "duration_minutes": log.duration_minutes,
            "efficiency": log.efficiency,
        }
        for log in logs
    ]


@router.get("/readiness")
async def readiness(
    start: datetime.date, end: datetime.date, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = await MetricsRepository(session).get_daily_range(provider=PROVIDER, start=start, end=end)
    return [
        {"date": row.date.isoformat(), "value": row.readiness_score, "source": row.readiness_source}
        for row in rows
    ]
