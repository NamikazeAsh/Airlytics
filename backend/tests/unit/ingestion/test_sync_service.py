import datetime

import pytest
import respx
from httpx import Response

from app.auth.token_service import PROVIDER, NotConnectedError
from app.core.security import encrypt
from app.ingestion.providers.google_health.client import BASE_URL
from app.ingestion.sync_service import DAILY_SUMMARY_METRIC_TYPE, sync_day, sync_day_tracked
from app.storage.repositories.metrics_repository import MetricsRepository
from app.storage.repositories.sync_state_repository import SyncStateRepository
from app.storage.repositories.token_repository import TokenRepository

from ._google_health_mocks import mock_defaults


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
async def test_sync_day_writes_steps_to_daily_metrics(db_session):
    await _seed_valid_token(db_session)
    date = datetime.date(2026, 7, 20)

    mock_defaults()
    respx.post(f"{BASE_URL}/users/me/dataTypes/steps/dataPoints:dailyRollUp").mock(
        return_value=Response(200, json={"rollupDataPoints": [{"steps": {"countSum": "9500"}}]})
    )

    await sync_day(db_session, date)

    rows = await MetricsRepository(db_session).get_daily_range(provider=PROVIDER, start=date, end=date)
    assert len(rows) == 1
    assert rows[0].steps_total == 9500


@respx.mock
async def test_sync_day_raises_without_connection(db_session):
    with pytest.raises(NotConnectedError):
        await sync_day(db_session, datetime.date(2026, 7, 20))


@respx.mock
async def test_sync_day_tracked_records_success(db_session):
    await _seed_valid_token(db_session)
    date = datetime.date(2026, 7, 20)
    mock_defaults()
    respx.post(f"{BASE_URL}/users/me/dataTypes/steps/dataPoints:dailyRollUp").mock(
        return_value=Response(200, json={"rollupDataPoints": [{"steps": {"countSum": "1000"}}]})
    )

    await sync_day_tracked(db_session, date)

    state = await SyncStateRepository(db_session).get(PROVIDER, DAILY_SUMMARY_METRIC_TYPE)
    assert state.status == "success"
    assert state.last_synced_date == date
    assert state.last_error is None


@respx.mock
async def test_sync_day_tracked_records_error_and_reraises(db_session):
    await _seed_valid_token(db_session)
    date = datetime.date(2026, 7, 20)
    mock_defaults()
    respx.post(f"{BASE_URL}/users/me/dataTypes/steps/dataPoints:dailyRollUp").mock(return_value=Response(400))

    with pytest.raises(Exception):
        await sync_day_tracked(db_session, date)

    state = await SyncStateRepository(db_session).get(PROVIDER, DAILY_SUMMARY_METRIC_TYPE)
    assert state.status == "error"
    assert state.last_error is not None
