import contextlib
import datetime

import respx
from httpx import Response

from app.auth.token_service import PROVIDER
from app.core.security import encrypt
from app.ingestion import sync_progress
from app.ingestion.manual_sync_service import run_manual_sync
from app.ingestion.providers.google_health.client import BASE_URL
from app.ingestion.sync_service import DAILY_SUMMARY_METRIC_TYPE
from app.storage.repositories.metrics_repository import MetricsRepository
from app.storage.repositories.sync_state_repository import SyncStateRepository
from app.storage.repositories.token_repository import TokenRepository

from ._google_health_mocks import mock_defaults

STEPS_URL = f"{BASE_URL}/users/me/dataTypes/steps/dataPoints:dailyRollUp"


def _session_factory(session):
    # run_manual_sync opens its own session via `async with async_session_factory() as s`;
    # wrap the test's shared db_session so entering/exiting the context doesn't close it.
    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return factory


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
async def test_run_manual_sync_catches_up_missing_days(db_session, monkeypatch):
    sync_progress.reset_progress()
    monkeypatch.setattr("app.ingestion.manual_sync_service.async_session_factory", _session_factory(db_session))

    await _seed_valid_token(db_session)
    mock_defaults()
    respx.post(STEPS_URL).mock(return_value=Response(200, json={"rollupDataPoints": [{"steps": {"countSum": "1"}}]}))

    today = datetime.date.today()
    await SyncStateRepository(db_session).upsert(
        provider=PROVIDER,
        metric_type=DAILY_SUMMARY_METRIC_TYPE,
        status="success",
        last_synced_date=today - datetime.timedelta(days=3),
    )

    await run_manual_sync()

    progress = sync_progress.get_progress()
    assert progress.status == "done"
    assert progress.total_days == 3

    rows = await MetricsRepository(db_session).get_daily_range(
        provider=PROVIDER, start=today - datetime.timedelta(days=2), end=today
    )
    assert len(rows) == 3


@respx.mock
async def test_run_manual_sync_stops_on_error(db_session, monkeypatch):
    sync_progress.reset_progress()
    monkeypatch.setattr("app.ingestion.manual_sync_service.async_session_factory", _session_factory(db_session))

    await _seed_valid_token(db_session)
    respx.post(STEPS_URL).mock(return_value=Response(400))

    today = datetime.date.today()
    await SyncStateRepository(db_session).upsert(
        provider=PROVIDER,
        metric_type=DAILY_SUMMARY_METRIC_TYPE,
        status="success",
        last_synced_date=today - datetime.timedelta(days=2),
    )

    await run_manual_sync()

    progress = sync_progress.get_progress()
    assert progress.status == "error"
    assert progress.error is not None

    rows = await MetricsRepository(db_session).get_daily_range(
        provider=PROVIDER, start=today - datetime.timedelta(days=1), end=today
    )
    assert len(rows) == 0


@respx.mock
async def test_run_manual_sync_noop_when_up_to_date(db_session, monkeypatch):
    sync_progress.reset_progress()
    monkeypatch.setattr("app.ingestion.manual_sync_service.async_session_factory", _session_factory(db_session))

    today = datetime.date.today()
    await SyncStateRepository(db_session).upsert(
        provider=PROVIDER, metric_type=DAILY_SUMMARY_METRIC_TYPE, status="success", last_synced_date=today
    )

    await run_manual_sync()

    progress = sync_progress.get_progress()
    assert progress.status == "done"
    assert progress.total_days == 0
