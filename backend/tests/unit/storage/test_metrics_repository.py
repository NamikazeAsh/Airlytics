import datetime

from app.storage.repositories.metrics_repository import MetricsRepository


async def test_upsert_daily_then_range_query(db_session):
    repo = MetricsRepository(db_session)

    await repo.upsert_daily(
        date=datetime.date(2026, 7, 20), provider="fitbit", steps_total=8000, resting_heart_rate=58
    )
    await repo.upsert_daily(
        date=datetime.date(2026, 7, 21), provider="fitbit", steps_total=9500, resting_heart_rate=56
    )
    await repo.upsert_daily(
        date=datetime.date(2026, 7, 22), provider="fitbit", steps_total=6000, resting_heart_rate=60
    )

    rows = await repo.get_daily_range(
        provider="fitbit", start=datetime.date(2026, 7, 20), end=datetime.date(2026, 7, 21)
    )

    assert [row.date for row in rows] == [datetime.date(2026, 7, 20), datetime.date(2026, 7, 21)]
    assert rows[0].steps_total == 8000
    assert rows[1].resting_heart_rate == 56


async def test_upsert_daily_updates_existing_row(db_session):
    repo = MetricsRepository(db_session)

    await repo.upsert_daily(date=datetime.date(2026, 7, 20), provider="fitbit", steps_total=8000)
    await repo.upsert_daily(date=datetime.date(2026, 7, 20), provider="fitbit", steps_total=8500)

    rows = await repo.get_daily_range(
        provider="fitbit", start=datetime.date(2026, 7, 20), end=datetime.date(2026, 7, 20)
    )
    assert len(rows) == 1
    assert rows[0].steps_total == 8500


async def test_get_daily_range_scoped_to_provider(db_session):
    repo = MetricsRepository(db_session)

    await repo.upsert_daily(date=datetime.date(2026, 7, 20), provider="fitbit", steps_total=8000)
    await repo.upsert_daily(date=datetime.date(2026, 7, 20), provider="oura", steps_total=100)

    rows = await repo.get_daily_range(
        provider="fitbit", start=datetime.date(2026, 7, 20), end=datetime.date(2026, 7, 20)
    )
    assert len(rows) == 1
    assert rows[0].provider == "fitbit"
