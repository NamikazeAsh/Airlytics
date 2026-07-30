import datetime

from app.analytics.rollups import _add_months, _month_start, _week_start, compute_rollups
from app.storage.repositories.metrics_repository import MetricsRepository
from app.storage.repositories.period_summary_repository import PeriodSummaryRepository

PROVIDER = "google_health"


def test_week_start_is_monday():
    assert _week_start(datetime.date(2026, 7, 23)) == datetime.date(2026, 7, 20)  # a Monday


def test_month_start():
    assert _month_start(datetime.date(2026, 7, 23)) == datetime.date(2026, 7, 1)


def test_add_months_handles_year_rollover():
    assert _add_months(datetime.date(2026, 1, 1), -1) == datetime.date(2025, 12, 1)
    assert _add_months(datetime.date(2026, 12, 1), 1) == datetime.date(2027, 1, 1)


async def test_compute_rollups_writes_weekly_and_monthly_summaries(db_session):
    repo = MetricsRepository(db_session)
    as_of = datetime.date(2026, 7, 23)
    week_start = _week_start(as_of)
    for i in range(7):
        await repo.upsert_daily(date=week_start + datetime.timedelta(days=i), provider=PROVIDER, steps_total=1000 + i * 100)

    await compute_rollups(db_session, PROVIDER, as_of=as_of)

    summaries = PeriodSummaryRepository(db_session)
    weekly = await summaries.get_range(PROVIDER, "weekly", "steps_total", week_start, week_start)
    assert len(weekly) == 1
    assert weekly[0].sample_count == 7
    assert weekly[0].avg_value == 1300.0
    assert weekly[0].min_value == 1000.0
    assert weekly[0].max_value == 1600.0

    month_start = as_of.replace(day=1)
    monthly = await summaries.get_range(PROVIDER, "monthly", "steps_total", month_start, month_start)
    assert len(monthly) == 1
    assert monthly[0].sample_count >= 7


async def test_compute_rollups_handles_period_with_no_data(db_session):
    as_of = datetime.date(2026, 7, 23)
    await compute_rollups(db_session, PROVIDER, as_of=as_of)

    summaries = PeriodSummaryRepository(db_session)
    week_start = _week_start(as_of)
    weekly = await summaries.get_range(PROVIDER, "weekly", "steps_total", week_start, week_start)
    assert len(weekly) == 1
    assert weekly[0].sample_count == 0
    assert weekly[0].avg_value is None
