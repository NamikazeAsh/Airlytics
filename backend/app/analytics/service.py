import dataclasses
import datetime

import numpy as np
import pandas as pd
from scipy.stats import linregress
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repositories.metrics_repository import MetricsRepository

METRICS = [
    "steps_total",
    "calories_total",
    "resting_heart_rate",
    "hrv_rmssd_avg",
    "spo2_avg",
    "sleep_duration_minutes",
    "sleep_efficiency",
    "active_minutes",
    "readiness_score",
]

STABLE_TREND_THRESHOLD_PCT = 3.0


@dataclasses.dataclass
class TrendResult:
    metric: str
    direction: str  # "increasing" | "decreasing" | "stable" | "insufficient_data"
    slope_per_day: float | None
    percent_change: float | None
    sample_count: int


@dataclasses.dataclass
class Anomaly:
    date: datetime.date
    metric: str
    value: float
    z_score: float
    baseline_mean: float
    baseline_stddev: float


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.metrics_repo = MetricsRepository(session)

    async def _dataframe(self, provider: str, start: datetime.date, end: datetime.date) -> pd.DataFrame:
        rows = await self.metrics_repo.get_daily_range(provider=provider, start=start, end=end)
        records = [{"date": r.date, **{m: getattr(r, m) for m in METRICS}} for r in rows]
        df = pd.DataFrame.from_records(records, columns=["date", *METRICS])
        if not df.empty:
            df = df.set_index("date")
        return df

    async def get_rolling_average(
        self, provider: str, metric: str, window_days: int, as_of: datetime.date | None = None
    ) -> float | None:
        as_of = as_of or datetime.date.today()
        start = as_of - datetime.timedelta(days=window_days - 1)
        df = await self._dataframe(provider, start, as_of)
        if df.empty or metric not in df:
            return None
        series = df[metric].dropna()
        if series.empty:
            return None
        return round(float(series.mean()), 2)

    async def get_trend(
        self, provider: str, metric: str, start: datetime.date, end: datetime.date
    ) -> TrendResult:
        df = await self._dataframe(provider, start, end)
        series = df[metric].dropna() if not df.empty and metric in df else pd.Series(dtype=float)

        if len(series) < 3:
            return TrendResult(metric, "insufficient_data", None, None, len(series))

        x = np.array([(d - series.index.min()).days for d in series.index], dtype=float)
        slope = float(linregress(x, series.values).slope)

        first_value = float(series.iloc[0])
        last_value = float(series.iloc[-1])

        if first_value == 0:
            percent_change = None
            direction = "stable"
        else:
            percent_change = round((last_value - first_value) / abs(first_value) * 100, 2)
            if abs(percent_change) < STABLE_TREND_THRESHOLD_PCT:
                direction = "stable"
            elif percent_change > 0:
                direction = "increasing"
            else:
                direction = "decreasing"

        return TrendResult(metric, direction, round(slope, 4), percent_change, len(series))

    async def get_zscore(
        self, provider: str, metric: str, date: datetime.date, baseline_days: int = 30
    ) -> float | None:
        baseline_start = date - datetime.timedelta(days=baseline_days)
        baseline_end = date - datetime.timedelta(days=1)
        df = await self._dataframe(provider, baseline_start, date)
        if df.empty or metric not in df or date not in df.index:
            return None

        today_value = df.loc[date, metric]
        if pd.isna(today_value):
            return None

        baseline = df.loc[baseline_start:baseline_end, metric].dropna()
        if len(baseline) < 5:
            return None

        std = float(baseline.std())
        if std == 0:
            return None
        return round((float(today_value) - float(baseline.mean())) / std, 3)

    async def get_anomalies(
        self,
        provider: str,
        start: datetime.date,
        end: datetime.date,
        baseline_days: int = 30,
        z_threshold: float = 2.0,
    ) -> list[Anomaly]:
        fetch_start = start - datetime.timedelta(days=baseline_days)
        df = await self._dataframe(provider, fetch_start, end)
        if df.empty:
            return []

        anomalies = []
        for metric in METRICS:
            if metric not in df:
                continue
            for date in df.index:
                if date < start or date > end:
                    continue
                value = df.loc[date, metric]
                if pd.isna(value):
                    continue
                baseline_start = date - datetime.timedelta(days=baseline_days)
                baseline_end = date - datetime.timedelta(days=1)
                baseline = df.loc[baseline_start:baseline_end, metric].dropna()
                if len(baseline) < 5:
                    continue
                std = float(baseline.std())
                if std == 0:
                    continue
                mean = float(baseline.mean())
                z = (float(value) - mean) / std
                if abs(z) >= z_threshold:
                    anomalies.append(Anomaly(date, metric, float(value), round(z, 3), round(mean, 2), round(std, 2)))

        return sorted(anomalies, key=lambda a: a.date)

    async def compare_periods(
        self,
        provider: str,
        metric: str,
        period_a_start: datetime.date,
        period_a_end: datetime.date,
        period_b_start: datetime.date,
        period_b_end: datetime.date,
    ) -> dict:
        df_a = await self._dataframe(provider, period_a_start, period_a_end)
        df_b = await self._dataframe(provider, period_b_start, period_b_end)

        mean_a = float(df_a[metric].dropna().mean()) if not df_a.empty and metric in df_a else None
        mean_b = float(df_b[metric].dropna().mean()) if not df_b.empty and metric in df_b else None

        delta = None
        percent_change = None
        if mean_a is not None and mean_b is not None:
            delta = round(mean_b - mean_a, 2)
            percent_change = round((mean_b - mean_a) / mean_a * 100, 2) if mean_a else None

        return {
            "metric": metric,
            "period_a_avg": round(mean_a, 2) if mean_a is not None else None,
            "period_b_avg": round(mean_b, 2) if mean_b is not None else None,
            "delta": delta,
            "percent_change": percent_change,
        }
