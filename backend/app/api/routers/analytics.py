import dataclasses
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import METRICS, AnalyticsService
from app.auth.token_service import PROVIDER
from app.core.database import get_session

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/trend")
async def trend(
    metric: str, start: datetime.date, end: datetime.date, session: AsyncSession = Depends(get_session)
) -> dict:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'. Valid: {METRICS}")

    result = await AnalyticsService(session).get_trend(PROVIDER, metric, start, end)
    return dataclasses.asdict(result)


@router.get("/anomalies")
async def anomalies(
    start: datetime.date,
    end: datetime.date,
    metric: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    results = await AnalyticsService(session).get_anomalies(PROVIDER, start, end)
    if metric is not None:
        results = [a for a in results if a.metric == metric]
    return [{**dataclasses.asdict(a), "date": a.date.isoformat()} for a in results]
