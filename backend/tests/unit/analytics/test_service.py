import datetime

import pytest

from app.analytics.service import AnalyticsService
from app.storage.repositories.metrics_repository import MetricsRepository

PROVIDER = "google_health"


async def _seed(session, field: str, values: dict):
    repo = MetricsRepository(session)
    for date, value in values.items():
        await repo.upsert_daily(date=date, provider=PROVIDER, **{field: value})


def _dates(start: datetime.date, n: int) -> list[datetime.date]:
    return [start + datetime.timedelta(days=i) for i in range(n)]


async def test_rolling_average_over_window(db_session):
    days = _dates(datetime.date(2026, 7, 1), 10)
    values = {d: 1000 + i * 100 for i, d in enumerate(days)}  # 1000..1900
    await _seed(db_session, "steps_total", values)

    avg = await AnalyticsService(db_session).get_rolling_average(
        PROVIDER, "steps_total", window_days=5, as_of=days[-1]
    )
    # last 5 values: 1500,1600,1700,1800,1900 -> mean 1700
    assert avg == 1700.0


async def test_rolling_average_no_data_returns_none(db_session):
    avg = await AnalyticsService(db_session).get_rolling_average(
        PROVIDER, "steps_total", window_days=5, as_of=datetime.date(2026, 7, 1)
    )
    assert avg is None


async def test_trend_increasing(db_session):
    days = _dates(datetime.date(2026, 7, 1), 10)
    values = {d: 1000 + i * 100 for i, d in enumerate(days)}
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).get_trend(PROVIDER, "steps_total", days[0], days[-1])
    assert result.direction == "increasing"
    assert result.slope_per_day == pytest.approx(100.0, abs=0.01)
    assert result.sample_count == 10
    # percent_change is first-value-to-last-value, not projected-swing-over-mean:
    # first=1000, last=1900 -> (1900-1000)/1000*100 = 90.0
    assert result.percent_change == pytest.approx(90.0, abs=0.01)


async def test_trend_percent_change_never_exceeds_100_for_volatile_short_window(db_session):
    # Reproduces the real bug: a noisy 7-day window used to report percent_change
    # of -104.6% (projected regression swing over mean), which is nonsensical for
    # a metric that only dropped from 12370 to 4850 (a ~61% drop, not >100%).
    days = _dates(datetime.date(2026, 7, 23), 7)
    raw_values = [12370, 16452, 2812, 3148, 3767, 8989, 4850]
    values = dict(zip(days, raw_values))
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).get_trend(PROVIDER, "steps_total", days[0], days[-1])
    expected = (4850 - 12370) / 12370 * 100
    assert result.percent_change == pytest.approx(expected, abs=0.01)
    assert -100 < result.percent_change < 0
    assert result.direction == "decreasing"


async def test_trend_stable(db_session):
    days = _dates(datetime.date(2026, 7, 1), 10)
    values = {d: 1000 for d in days}
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).get_trend(PROVIDER, "steps_total", days[0], days[-1])
    assert result.direction == "stable"
    assert result.slope_per_day == pytest.approx(0.0, abs=0.01)


async def test_trend_percent_change_none_when_first_value_zero(db_session):
    days = _dates(datetime.date(2026, 7, 1), 5)
    values = {days[0]: 0, days[1]: 10, days[2]: 5, days[3]: 8, days[4]: 12}
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).get_trend(PROVIDER, "steps_total", days[0], days[-1])
    assert result.percent_change is None
    assert result.direction == "stable"


async def test_trend_decreasing(db_session):
    days = _dates(datetime.date(2026, 7, 1), 10)
    values = {d: 2000 - i * 100 for i, d in enumerate(days)}
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).get_trend(PROVIDER, "steps_total", days[0], days[-1])
    assert result.direction == "decreasing"


async def test_trend_insufficient_data(db_session):
    days = _dates(datetime.date(2026, 7, 1), 2)
    values = {d: 1000 for d in days}
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).get_trend(PROVIDER, "steps_total", days[0], days[-1])
    assert result.direction == "insufficient_data"


async def test_zscore_hand_computed(db_session):
    # baseline mean=50, sample std=1.5811388300841898 (ddof=1); today=53
    baseline_start = datetime.date(2026, 7, 5)
    baseline_values = [50, 52, 48, 51, 49]
    values = {baseline_start + datetime.timedelta(days=i): v for i, v in enumerate(baseline_values)}
    today = datetime.date(2026, 7, 10)
    values[today] = 53
    await _seed(db_session, "resting_heart_rate", values)

    z = await AnalyticsService(db_session).get_zscore(PROVIDER, "resting_heart_rate", today, baseline_days=5)
    expected = (53 - 50) / 1.5811388300841898
    assert z == pytest.approx(expected, abs=0.001)


async def test_zscore_insufficient_baseline_returns_none(db_session):
    today = datetime.date(2026, 7, 10)
    await _seed(db_session, "resting_heart_rate", {today: 60})
    z = await AnalyticsService(db_session).get_zscore(PROVIDER, "resting_heart_rate", today, baseline_days=30)
    assert z is None


async def test_anomalies_flags_clear_outlier(db_session):
    baseline_start = datetime.date(2026, 7, 1)
    baseline_values = [50, 52, 48, 51, 49]
    values = {baseline_start + datetime.timedelta(days=i): v for i, v in enumerate(baseline_values)}
    outlier_date = datetime.date(2026, 7, 10)
    values[outlier_date] = 90
    await _seed(db_session, "resting_heart_rate", values)

    anomalies = await AnalyticsService(db_session).get_anomalies(
        PROVIDER, start=outlier_date, end=outlier_date, baseline_days=30
    )
    assert len(anomalies) == 1
    assert anomalies[0].date == outlier_date
    assert anomalies[0].metric == "resting_heart_rate"
    assert anomalies[0].value == 90


async def test_anomalies_no_flag_within_normal_range(db_session):
    baseline_start = datetime.date(2026, 7, 1)
    baseline_values = [50, 52, 48, 51, 49]
    values = {baseline_start + datetime.timedelta(days=i): v for i, v in enumerate(baseline_values)}
    normal_date = datetime.date(2026, 7, 10)
    values[normal_date] = 51
    await _seed(db_session, "resting_heart_rate", values)

    anomalies = await AnalyticsService(db_session).get_anomalies(
        PROVIDER, start=normal_date, end=normal_date, baseline_days=30
    )
    assert anomalies == []


async def test_compare_periods(db_session):
    period_a = _dates(datetime.date(2026, 6, 1), 5)
    period_b = _dates(datetime.date(2026, 7, 1), 5)
    values = {d: 1000 for d in period_a} | {d: 1500 for d in period_b}
    await _seed(db_session, "steps_total", values)

    result = await AnalyticsService(db_session).compare_periods(
        PROVIDER, "steps_total", period_a[0], period_a[-1], period_b[0], period_b[-1]
    )
    assert result["period_a_avg"] == 1000.0
    assert result["period_b_avg"] == 1500.0
    assert result["delta"] == 500.0
    assert result["percent_change"] == 50.0
