import datetime

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repositories.metrics_repository import MetricsRepository

# Lag-1 features: yesterday's HRV/RHR/sleep-efficiency, plus yesterday's readiness itself
# (the persistence feature, and also what the naive baseline predicts from). Kept small
# deliberately - the labeled dataset is only ~50 rows, so a handful of parameters is already
# pushing it for a linear model.
LAG_FIELDS = ["hrv_rmssd_avg", "resting_heart_rate", "sleep_efficiency", "readiness_score"]
TARGET_FIELD = "readiness_score"

EARLIEST_DATE = datetime.date(2000, 1, 1)


def _is_complete(row) -> bool:
    return all(getattr(row, field) is not None for field in LAG_FIELDS)


async def _rows_by_date(session: AsyncSession, provider: str) -> dict[datetime.date, object]:
    rows = await MetricsRepository(session).get_daily_range(provider, EARLIEST_DATE, datetime.date.today())
    return {row.date: row for row in rows}


async def build_dataset(session: AsyncSession, provider: str) -> pd.DataFrame:
    """One row per day with a readiness score, features from the previous day."""
    by_date = await _rows_by_date(session, provider)

    records = []
    for date, row in by_date.items():
        if row.readiness_score is None:
            continue
        prev = by_date.get(date - datetime.timedelta(days=1))
        if prev is None or not _is_complete(prev):
            continue
        record = {f"{field}_lag1": getattr(prev, field) for field in LAG_FIELDS}
        record["date"] = date
        record[TARGET_FIELD] = row.readiness_score
        records.append(record)

    df = pd.DataFrame.from_records(records)
    if not df.empty:
        df = df.set_index("date").sort_index()
    return df


async def latest_complete_features(
    session: AsyncSession, provider: str
) -> tuple[datetime.date, dict[str, float]] | None:
    """Most recent day with a full metric set, as lag-1 features for a live prediction."""
    by_date = await _rows_by_date(session, provider)
    for date in sorted(by_date, reverse=True):
        row = by_date[date]
        if _is_complete(row):
            return date, {f"{field}_lag1": getattr(row, field) for field in LAG_FIELDS}
    return None
