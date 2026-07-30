import datetime

from app.storage.models import ActivityLog
from app.storage.repositories.activity_repository import ActivityRepository


async def test_upsert_then_query(db_session):
    repo = ActivityRepository(db_session)
    await repo.upsert(
        external_activity_id="users/123/dataTypes/exercise/dataPoints/def",
        provider="google_health",
        date=datetime.date(2026, 7, 23),
        activity_type="WALKING",
        start_time=datetime.datetime(2026, 7, 23, 17, 7),
        duration_minutes=24,
        calories=198,
        avg_heart_rate=101,
        distance_km=1.7015,
    )

    result = await db_session.get(ActivityLog, "users/123/dataTypes/exercise/dataPoints/def")
    assert result.activity_type == "WALKING"
    assert result.calories == 198
    assert result.distance_km == 1.7015


async def test_upsert_overwrites_existing_activity(db_session):
    repo = ActivityRepository(db_session)
    kwargs = dict(
        external_activity_id="users/123/dataTypes/exercise/dataPoints/def",
        provider="google_health",
        date=datetime.date(2026, 7, 23),
        activity_type="WALKING",
        start_time=datetime.datetime(2026, 7, 23, 17, 7),
    )
    await repo.upsert(**kwargs, calories=198)
    await repo.upsert(**kwargs, calories=210)

    result = await db_session.get(ActivityLog, "users/123/dataTypes/exercise/dataPoints/def")
    assert result.calories == 210
