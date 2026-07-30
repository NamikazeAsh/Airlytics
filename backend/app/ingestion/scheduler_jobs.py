import datetime
import logging

from app.ai_coach.insights_service import generate_insights
from app.analytics.readiness import update_readiness_for_date
from app.analytics.rollups import compute_rollups
from app.auth.token_service import PROVIDER, NotConnectedError, get_valid_access_token
from app.core.database import async_session_factory
from app.core.scheduler import scheduler
from app.ingestion.backfill_service import run_backfill_step
from app.ingestion.sync_service import sync_day_tracked

logger = logging.getLogger(__name__)

READINESS_CATCHUP_DAYS = 90


async def sync_daily_summary_job() -> None:
    async with async_session_factory() as session:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        try:
            await sync_day_tracked(session, yesterday)
        except NotConnectedError:
            pass


async def refresh_token_check_job() -> None:
    async with async_session_factory() as session:
        try:
            await get_valid_access_token(session)
        except NotConnectedError:
            pass


async def backfill_continuation_job() -> None:
    async with async_session_factory() as session:
        await run_backfill_step(session)


async def nightly_rollups_job() -> None:
    async with async_session_factory() as session:
        today = datetime.date.today()
        for i in range(1, READINESS_CATCHUP_DAYS + 1):
            await update_readiness_for_date(session, PROVIDER, today - datetime.timedelta(days=i))
        await compute_rollups(session, PROVIDER, as_of=today)

    async with async_session_factory() as session:
        try:
            await generate_insights(session)
        except Exception:
            logger.exception("Nightly insight generation failed")


def register_jobs() -> None:
    scheduler.add_job(sync_daily_summary_job, "interval", hours=24, id="sync_daily_summary", replace_existing=True)
    scheduler.add_job(refresh_token_check_job, "interval", hours=1, id="refresh_token_check", replace_existing=True)
    scheduler.add_job(
        backfill_continuation_job, "interval", minutes=5, id="backfill_continuation", replace_existing=True
    )
    scheduler.add_job(nightly_rollups_job, "interval", hours=24, id="nightly_rollups", replace_existing=True)
