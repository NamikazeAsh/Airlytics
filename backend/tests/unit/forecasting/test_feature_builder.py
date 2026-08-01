import datetime

from app.forecasting.feature_builder import build_dataset, latest_complete_features
from app.storage.repositories.metrics_repository import MetricsRepository

PROVIDER = "google_health"


async def _seed(session, date: datetime.date, **fields) -> None:
    await MetricsRepository(session).upsert_daily(date=date, provider=PROVIDER, **fields)


async def test_build_dataset_requires_complete_predecessor(db_session):
    day1 = datetime.date(2026, 1, 1)
    day2 = day1 + datetime.timedelta(days=1)
    day3 = day2 + datetime.timedelta(days=1)
    # day4 intentionally missing (gap)
    day5 = day1 + datetime.timedelta(days=4)

    await _seed(db_session, day1, hrv_rmssd_avg=40, resting_heart_rate=60, sleep_efficiency=85, readiness_score=55)
    await _seed(db_session, day2, hrv_rmssd_avg=42, resting_heart_rate=58, sleep_efficiency=88, readiness_score=60)
    # day3 has a readiness score but is missing hrv - still a valid target (only day3's predecessor,
    # day2, needs to be complete), just not usable as someone else's predecessor.
    await _seed(db_session, day3, resting_heart_rate=59, sleep_efficiency=87, readiness_score=50)
    await _seed(db_session, day5, hrv_rmssd_avg=41, resting_heart_rate=61, sleep_efficiency=86, readiness_score=52)

    df = await build_dataset(db_session, PROVIDER)

    assert list(df.index) == [day2, day3]
    assert df.loc[day2, "hrv_rmssd_avg_lag1"] == 40
    assert df.loc[day2, "readiness_score_lag1"] == 55
    assert df.loc[day2, "readiness_score"] == 60
    assert df.loc[day3, "hrv_rmssd_avg_lag1"] == 42
    assert df.loc[day3, "readiness_score"] == 50


async def test_latest_complete_features_returns_most_recent_complete_day(db_session):
    day1 = datetime.date(2026, 2, 1)
    day2 = day1 + datetime.timedelta(days=1)

    await _seed(db_session, day1, hrv_rmssd_avg=40, resting_heart_rate=60, sleep_efficiency=85, readiness_score=55)
    # day2 is the most recent day but is missing a field - should be skipped in favor of day1.
    await _seed(db_session, day2, hrv_rmssd_avg=41, resting_heart_rate=61, sleep_efficiency=None, readiness_score=56)

    result = await latest_complete_features(db_session, PROVIDER)

    assert result is not None
    date, features = result
    assert date == day1
    assert features["hrv_rmssd_avg_lag1"] == 40
    assert features["readiness_score_lag1"] == 55


async def test_latest_complete_features_returns_none_when_no_data(db_session):
    result = await latest_complete_features(db_session, PROVIDER)
    assert result is None
