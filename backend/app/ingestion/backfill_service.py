import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import PROVIDER
from app.config import get_settings
from app.ingestion.sync_service import sync_day
from app.storage.repositories.sync_state_repository import SyncStateRepository

METRIC_TYPE = "backfill"
BATCH_SIZE_DAYS = 5


async def start_backfill(session: AsyncSession) -> None:
    repo = SyncStateRepository(session)
    existing = await repo.get(PROVIDER, METRIC_TYPE)
    if existing is not None and existing.status == "completed":
        return

    start_date = datetime.date.today() - datetime.timedelta(days=1)
    await repo.upsert(
        provider=PROVIDER,
        metric_type=METRIC_TYPE,
        status="running",
        cursor={"next_date": start_date.isoformat()},
    )


async def run_backfill_step(session: AsyncSession) -> None:
    repo = SyncStateRepository(session)
    state = await repo.get(PROVIDER, METRIC_TYPE)
    if state is None or state.status == "completed":
        return

    oldest_date = datetime.date.today() - datetime.timedelta(days=get_settings().max_backfill_days)
    next_date = datetime.date.fromisoformat(state.cursor["next_date"])

    for _ in range(BATCH_SIZE_DAYS):
        if next_date < oldest_date:
            await repo.upsert(provider=PROVIDER, metric_type=METRIC_TYPE, status="completed", cursor=None)
            return

        try:
            await sync_day(session, next_date)
        except Exception as exc:
            await repo.upsert(
                provider=PROVIDER,
                metric_type=METRIC_TYPE,
                status="error",
                last_error=f"{type(exc).__name__}: {exc}",
                cursor={"next_date": next_date.isoformat()},
            )
            return

        next_date -= datetime.timedelta(days=1)

    await repo.upsert(
        provider=PROVIDER,
        metric_type=METRIC_TYPE,
        status="running",
        cursor={"next_date": next_date.isoformat()},
    )
