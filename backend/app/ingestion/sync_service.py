import dataclasses
import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import PROVIDER, NotConnectedError, get_valid_access_token
from app.ingestion.providers.google_health import mappers
from app.ingestion.providers.google_health.client import (
    GoogleHealthClient,
    daily_summary_date_filter,
    session_civil_start_filter,
    sleep_civil_end_filter,
)
from app.storage.repositories.activity_repository import ActivityRepository
from app.storage.repositories.metrics_repository import MetricsRepository
from app.storage.repositories.sleep_repository import SleepRepository
from app.storage.repositories.sync_state_repository import SyncStateRepository

DAILY_SUMMARY_METRIC_TYPE = "daily_summary"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


async def sync_day(session: AsyncSession, date: datetime.date) -> None:
    access_token = await get_valid_access_token(session)
    client = GoogleHealthClient(access_token)
    next_date = date + datetime.timedelta(days=1)

    steps_rollup = await client.daily_rollup("steps", date, next_date)
    summary = mappers.map_daily_summary(date, steps_rollup)

    calories_rollup = await client.daily_rollup("total-calories", date, next_date)
    summary.calories_total = mappers.extract_total_calories(calories_rollup)

    active_minutes_rollup = await client.daily_rollup("active-minutes", date, next_date)
    summary.active_minutes = mappers.extract_active_minutes(active_minutes_rollup)

    resting_hr_response = await client.reconcile(
        "daily-resting-heart-rate", daily_summary_date_filter("daily-resting-heart-rate", date)
    )
    summary.resting_heart_rate = mappers.extract_daily_resting_heart_rate(resting_hr_response)

    hrv_response = await client.reconcile(
        "daily-heart-rate-variability", daily_summary_date_filter("daily-heart-rate-variability", date)
    )
    summary.hrv_rmssd_avg = mappers.extract_daily_hrv(hrv_response)

    spo2_response = await client.reconcile(
        "daily-oxygen-saturation", daily_summary_date_filter("daily-oxygen-saturation", date)
    )
    summary.spo2_avg, summary.spo2_min = mappers.extract_daily_spo2(spo2_response)

    sleep_response = await client.reconcile("sleep", sleep_civil_end_filter(date))
    summary.sleep_duration_minutes, summary.sleep_efficiency = mappers.extract_main_sleep(sleep_response)

    sleep_repo = SleepRepository(session)
    for point in sleep_response.get("dataPoints", []):
        await sleep_repo.upsert(provider=PROVIDER, **mappers.map_sleep_log(point, date))

    exercise_response = await client.reconcile("exercise", session_civil_start_filter("exercise", date))
    activity_repo = ActivityRepository(session)
    for point in exercise_response.get("dataPoints", []):
        await activity_repo.upsert(provider=PROVIDER, **mappers.map_activity_log(point, date))

    summary.raw_payload = {
        "steps": steps_rollup,
        "total_calories": calories_rollup,
        "active_minutes": active_minutes_rollup,
        "daily_resting_heart_rate": resting_hr_response,
        "daily_heart_rate_variability": hrv_response,
        "daily_oxygen_saturation": spo2_response,
        "sleep": sleep_response,
        "exercise": exercise_response,
    }

    fields = {k: v for k, v in dataclasses.asdict(summary).items() if k not in ("date",) and v is not None}
    await MetricsRepository(session).upsert_daily(date=date, provider=PROVIDER, **fields)


async def sync_day_tracked(session: AsyncSession, date: datetime.date) -> None:
    # records outcome in sync_state, so GET /api/sync/status reflects the last real attempt
    repo = SyncStateRepository(session)
    try:
        await sync_day(session, date)
    except NotConnectedError:
        raise
    except Exception as exc:
        # Preserve the last *successful* sync date on failure - repo.upsert always
        # overwrites last_synced_date, and advancing it to the failing date would make
        # manual_sync_service think this day already succeeded and skip retrying it.
        existing = await repo.get(PROVIDER, DAILY_SUMMARY_METRIC_TYPE)
        await repo.upsert(
            provider=PROVIDER,
            metric_type=DAILY_SUMMARY_METRIC_TYPE,
            status="error",
            last_synced_date=existing.last_synced_date if existing else None,
            # str(exc) is empty for some exceptions (e.g. asyncio.TimeoutError), so include
            # the type name too - otherwise the recorded error is a blank, useless string.
            last_error=f"{type(exc).__name__}: {exc}",
        )
        raise

    await repo.upsert(
        provider=PROVIDER,
        metric_type=DAILY_SUMMARY_METRIC_TYPE,
        status="success",
        last_synced_date=date,
        last_synced_at=_now(),
    )
