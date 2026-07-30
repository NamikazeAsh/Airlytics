import datetime

import respx
from httpx import Response

from app.auth.token_service import PROVIDER
from app.core.security import encrypt
from app.ingestion.backfill_service import METRIC_TYPE, run_backfill_step, start_backfill
from app.ingestion.providers.google_health.client import BASE_URL
from app.storage.repositories.metrics_repository import MetricsRepository
from app.storage.repositories.sync_state_repository import SyncStateRepository
from app.storage.repositories.token_repository import TokenRepository

from ._google_health_mocks import mock_defaults

STEPS_URL = f"{BASE_URL}/users/me/dataTypes/steps/dataPoints:dailyRollUp"


async def _seed_valid_token(session):
    far_future = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=1)
    await TokenRepository(session).upsert(
        provider=PROVIDER,
        access_token_encrypted=encrypt("access-token"),
        refresh_token_encrypted=encrypt("refresh-token"),
        scope="activity_and_fitness.readonly",
        expires_at=far_future,
        external_user_id="me",
    )


@respx.mock
async def test_run_backfill_step_processes_one_batch_and_advances_cursor(db_session):
    await _seed_valid_token(db_session)
    mock_defaults()
    respx.post(STEPS_URL).mock(return_value=Response(200, json={"rollupDataPoints": [{"steps": {"countSum": "1"}}]}))

    await start_backfill(db_session)
    state_before = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    start_next_date = datetime.date.fromisoformat(state_before.cursor["next_date"])

    await run_backfill_step(db_session)

    state_after = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    assert state_after.status == "running"
    next_date_after = datetime.date.fromisoformat(state_after.cursor["next_date"])
    assert next_date_after == start_next_date - datetime.timedelta(days=5)

    rows = await MetricsRepository(db_session).get_daily_range(
        provider=PROVIDER, start=next_date_after + datetime.timedelta(days=1), end=start_next_date
    )
    assert len(rows) == 5


@respx.mock
async def test_run_backfill_step_resumes_from_cursor_across_calls(db_session):
    await _seed_valid_token(db_session)
    mock_defaults()
    respx.post(STEPS_URL).mock(return_value=Response(200, json={"rollupDataPoints": [{"steps": {"countSum": "1"}}]}))

    await start_backfill(db_session)
    await run_backfill_step(db_session)
    state_after_first = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    cursor_after_first = state_after_first.cursor["next_date"]

    await run_backfill_step(db_session)
    state_after_second = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    cursor_after_second = state_after_second.cursor["next_date"]

    assert cursor_after_second != cursor_after_first
    assert datetime.date.fromisoformat(cursor_after_second) < datetime.date.fromisoformat(cursor_after_first)


@respx.mock
async def test_run_backfill_step_marks_completed_past_oldest_date(db_session):
    await _seed_valid_token(db_session)
    respx.post(STEPS_URL).mock(return_value=Response(200, json={"rollupDataPoints": [{"steps": {"countSum": "1"}}]}))

    repo = SyncStateRepository(db_session)
    await repo.upsert(
        provider=PROVIDER,
        metric_type=METRIC_TYPE,
        status="running",
        cursor={"next_date": (datetime.date.today() - datetime.timedelta(days=370)).isoformat()},
    )

    await run_backfill_step(db_session)

    state = await repo.get(PROVIDER, METRIC_TYPE)
    assert state.status == "completed"
    assert state.cursor is None


@respx.mock
async def test_run_backfill_step_records_error_and_preserves_cursor(db_session):
    await _seed_valid_token(db_session)
    respx.post(STEPS_URL).mock(return_value=Response(400))

    await start_backfill(db_session)
    state_before = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    failing_date = state_before.cursor["next_date"]

    await run_backfill_step(db_session)

    state_after = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    assert state_after.status == "error"
    assert state_after.last_error is not None
    assert state_after.cursor["next_date"] == failing_date


@respx.mock
async def test_run_backfill_step_noop_when_no_state(db_session):
    await run_backfill_step(db_session)
    state = await SyncStateRepository(db_session).get(PROVIDER, METRIC_TYPE)
    assert state is None


@respx.mock
async def test_start_backfill_skips_if_already_completed(db_session):
    repo = SyncStateRepository(db_session)
    await repo.upsert(provider=PROVIDER, metric_type=METRIC_TYPE, status="completed", cursor=None)

    await start_backfill(db_session)

    state = await repo.get(PROVIDER, METRIC_TYPE)
    assert state.status == "completed"
    assert state.cursor is None
