import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import PROVIDER, NotConnectedError
from app.core.database import get_session
from app.ingestion.sync_service import sync_day_tracked
from app.storage.repositories.sync_state_repository import SyncStateRepository

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/trigger")
async def trigger(
    date: datetime.date | None = None, session: AsyncSession = Depends(get_session)
) -> dict:
    target_date = date or datetime.date.today() - datetime.timedelta(days=1)
    try:
        await sync_day_tracked(session, target_date)
    except NotConnectedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"date": target_date.isoformat(), "status": "synced"}


@router.get("/status")
async def status(session: AsyncSession = Depends(get_session)) -> list[dict]:
    states = await SyncStateRepository(session).get_all_for_provider(PROVIDER)
    return [
        {
            "metric_type": s.metric_type,
            "status": s.status,
            "last_synced_date": s.last_synced_date.isoformat() if s.last_synced_date else None,
            "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
            "last_error": s.last_error,
        }
        for s in states
    ]
