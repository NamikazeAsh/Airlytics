import datetime

from app.storage.repositories.sync_state_repository import SyncStateRepository


async def test_upsert_then_get(db_session):
    repo = SyncStateRepository(db_session)
    synced_at = datetime.datetime(2026, 7, 24, 3, 0)

    await repo.upsert(
        provider="fitbit",
        metric_type="daily_summary",
        status="success",
        last_synced_date=datetime.date(2026, 7, 23),
        last_synced_at=synced_at,
        cursor={"day": "2026-07-23"},
    )

    state = await repo.get("fitbit", "daily_summary")
    assert state is not None
    assert state.status == "success"
    assert state.last_synced_date == datetime.date(2026, 7, 23)
    assert state.cursor == {"day": "2026-07-23"}


async def test_upsert_records_error_status(db_session):
    repo = SyncStateRepository(db_session)

    await repo.upsert(
        provider="fitbit", metric_type="intraday_heart_rate", status="error", last_error="rate limited"
    )

    state = await repo.get("fitbit", "intraday_heart_rate")
    assert state.status == "error"
    assert state.last_error == "rate limited"


async def test_get_missing_state_returns_none(db_session):
    repo = SyncStateRepository(db_session)
    assert await repo.get("oura", "daily_summary") is None
