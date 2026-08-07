import datetime

from app.analytics.readiness import update_readiness_for_date
from app.auth.token_service import PROVIDER
from app.core.database import async_session_factory
from app.ingestion import sync_progress
from app.ingestion.sync_service import DAILY_SUMMARY_METRIC_TYPE, sync_day_tracked
from app.storage.repositories.sync_state_repository import SyncStateRepository


async def run_manual_sync() -> None:
    async with async_session_factory() as session:
        state = await SyncStateRepository(session).get(PROVIDER, DAILY_SUMMARY_METRIC_TYPE)
        today = datetime.date.today()
        start_date = state.last_synced_date + datetime.timedelta(days=1) if state and state.last_synced_date else today

        if start_date > today:
            sync_progress.update_progress(status="done", stage="", day_index=0, total_days=0, error=None)
            return

        days = [start_date + datetime.timedelta(days=i) for i in range((today - start_date).days + 1)]
        sync_progress.update_progress(status="running", stage="syncing", day_index=0, total_days=len(days), error=None)

        for i, day in enumerate(days, start=1):
            sync_progress.update_progress(day_index=i, current_day=day.isoformat())
            try:
                await sync_day_tracked(session, day)
            except Exception as exc:
                sync_progress.update_progress(status="error", error=f"{type(exc).__name__}: {exc}")
                return

        sync_progress.update_progress(stage="computing_readiness")
        for day in days:
            await update_readiness_for_date(session, PROVIDER, day)

        sync_progress.update_progress(status="done", stage="")
