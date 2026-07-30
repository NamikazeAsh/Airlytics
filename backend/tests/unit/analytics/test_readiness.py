import datetime

import pytest

from app.analytics.readiness import compute_readiness_score, update_readiness_for_date
from app.storage.repositories.metrics_repository import MetricsRepository

PROVIDER = "google_health"
BASELINE_VALUES = [50, 52, 48, 51, 49]  # mean 50, sample std ~1.5811388300841898
BASELINE_STD = 1.5811388300841898


async def _seed_baseline_and_today(session, today: datetime.date, today_value: float):
    repo = MetricsRepository(session)
    baseline_start = today - datetime.timedelta(days=5)
    for i, v in enumerate(BASELINE_VALUES):
        date = baseline_start + datetime.timedelta(days=i)
        await repo.upsert_daily(
            date=date, provider=PROVIDER, hrv_rmssd_avg=v, resting_heart_rate=v, sleep_efficiency=v
        )
    await repo.upsert_daily(
        date=today,
        provider=PROVIDER,
        hrv_rmssd_avg=today_value,
        resting_heart_rate=today_value,
        sleep_efficiency=today_value,
    )


async def test_compute_readiness_score_hand_computed(db_session):
    today = datetime.date(2026, 7, 10)
    await _seed_baseline_and_today(db_session, today, today_value=53)

    z = (53 - 50) / BASELINE_STD
    expected_weighted = 0.4 * z + (-0.3) * z + 0.3 * z
    expected_score = round(max(0.0, min(100.0, 50 + expected_weighted * 15)), 1)

    score = await compute_readiness_score(db_session, PROVIDER, today, baseline_days=5)
    assert score == pytest.approx(expected_score, abs=0.01)


async def test_compute_readiness_returns_none_without_baseline(db_session):
    repo = MetricsRepository(db_session)
    today = datetime.date(2026, 7, 10)
    await repo.upsert_daily(date=today, provider=PROVIDER, hrv_rmssd_avg=50)

    score = await compute_readiness_score(db_session, PROVIDER, today, baseline_days=30)
    assert score is None


async def test_update_readiness_for_date_persists_score(db_session):
    today = datetime.date(2026, 7, 10)
    await _seed_baseline_and_today(db_session, today, today_value=53)

    score = await update_readiness_for_date(db_session, PROVIDER, today)
    assert score is not None

    rows = await MetricsRepository(db_session).get_daily_range(provider=PROVIDER, start=today, end=today)
    assert rows[0].readiness_score == score
    assert rows[0].readiness_source == "computed_fallback"
