import datetime

from app.storage.models import SleepLog
from app.storage.repositories.sleep_repository import SleepRepository


async def test_upsert_then_query(db_session):
    repo = SleepRepository(db_session)
    await repo.upsert(
        external_log_id="users/123/dataTypes/sleep/dataPoints/abc",
        provider="google_health",
        date=datetime.date(2026, 7, 23),
        start_time=datetime.datetime(2026, 7, 23, 23, 0),
        end_time=datetime.datetime(2026, 7, 24, 6, 30),
        duration_minutes=400,
        efficiency=89,
        stages=[{"type": "DEEP", "minutes": 60}],
    )

    result = await db_session.get(SleepLog, "users/123/dataTypes/sleep/dataPoints/abc")
    assert result.duration_minutes == 400
    assert result.efficiency == 89
    assert result.stages == [{"type": "DEEP", "minutes": 60}]


async def test_upsert_overwrites_existing_log(db_session):
    repo = SleepRepository(db_session)
    kwargs = dict(
        external_log_id="users/123/dataTypes/sleep/dataPoints/abc",
        provider="google_health",
        date=datetime.date(2026, 7, 23),
        start_time=datetime.datetime(2026, 7, 23, 23, 0),
        end_time=datetime.datetime(2026, 7, 24, 6, 30),
    )
    await repo.upsert(**kwargs, duration_minutes=400, efficiency=89)
    await repo.upsert(**kwargs, duration_minutes=410, efficiency=91)

    result = await db_session.get(SleepLog, "users/123/dataTypes/sleep/dataPoints/abc")
    assert result.duration_minutes == 410
    assert result.efficiency == 91
