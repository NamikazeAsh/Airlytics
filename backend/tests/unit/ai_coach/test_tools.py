import datetime

import pytest

from app.ai_coach.tools import TOOL_SPECS, execute_tool
from app.auth.token_service import PROVIDER
from app.storage.repositories.metrics_repository import MetricsRepository


async def _seed(session, field: str, values: dict):
    repo = MetricsRepository(session)
    for date, value in values.items():
        await repo.upsert_daily(date=date, provider=PROVIDER, **{field: value})


def test_tool_specs_have_unique_names():
    names = [t.name for t in TOOL_SPECS]
    assert len(names) == len(set(names))


async def test_get_metric_series(db_session):
    days = [datetime.date(2026, 7, 1) + datetime.timedelta(days=i) for i in range(3)]
    await _seed(db_session, "steps_total", {d: 1000 * (i + 1) for i, d in enumerate(days)})

    result = await execute_tool(
        db_session, "get_metric_series", {"metric": "steps_total", "start": "2026-07-01", "end": "2026-07-03"}
    )
    assert result["series"] == [
        {"date": "2026-07-01", "value": 1000},
        {"date": "2026-07-02", "value": 2000},
        {"date": "2026-07-03", "value": 3000},
    ]


async def test_get_rolling_average(db_session):
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(3)]
    await _seed(db_session, "steps_total", {d: 1000 for d in days})

    result = await execute_tool(db_session, "get_rolling_average", {"metric": "steps_total", "window_days": 3})
    assert result == {"average": 1000.0}


async def test_get_trend(db_session):
    days = [datetime.date(2026, 7, 1) + datetime.timedelta(days=i) for i in range(5)]
    await _seed(db_session, "steps_total", {d: 1000 + i * 100 for i, d in enumerate(days)})

    result = await execute_tool(
        db_session, "get_trend", {"metric": "steps_total", "start": "2026-07-01", "end": "2026-07-05"}
    )
    assert result["direction"] == "increasing"
    assert result["sample_count"] == 5


async def test_get_anomalies(db_session):
    # baseline must vary (std > 0) or the detector correctly skips it as undefined
    days = [datetime.date(2026, 7, 1) + datetime.timedelta(days=i) for i in range(6)]
    baseline_values = [50, 52, 48, 51, 49]
    values = dict(zip(days[:5], baseline_values))
    values[days[5]] = 200
    await _seed(db_session, "resting_heart_rate", values)

    result = await execute_tool(db_session, "get_anomalies", {"start": "2026-07-06", "end": "2026-07-06"})
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["metric"] == "resting_heart_rate"


async def test_compare_periods(db_session):
    period_a = [datetime.date(2026, 6, 1) + datetime.timedelta(days=i) for i in range(3)]
    period_b = [datetime.date(2026, 7, 1) + datetime.timedelta(days=i) for i in range(3)]
    await _seed(db_session, "steps_total", {d: 1000 for d in period_a} | {d: 2000 for d in period_b})

    result = await execute_tool(
        db_session,
        "compare_periods",
        {
            "metric": "steps_total",
            "period_a_start": "2026-06-01",
            "period_a_end": "2026-06-03",
            "period_b_start": "2026-07-01",
            "period_b_end": "2026-07-03",
        },
    )
    assert result["period_a_avg"] == 1000.0
    assert result["period_b_avg"] == 2000.0


async def test_get_readiness_explanation(db_session):
    repo = MetricsRepository(db_session)
    date = datetime.date(2026, 7, 10)
    await repo.upsert_daily(date=date, provider=PROVIDER, readiness_score=55.0, readiness_source="computed_fallback")

    result = await execute_tool(db_session, "get_readiness_explanation", {"date": "2026-07-10"})
    assert result["readiness_score"] == 55.0
    assert set(result["baseline_deviation_z_scores"].keys()) == {
        "hrv_rmssd_avg",
        "resting_heart_rate",
        "sleep_efficiency",
    }


async def test_execute_tool_unknown_name_raises(db_session):
    with pytest.raises(ValueError):
        await execute_tool(db_session, "not_a_real_tool", {})
