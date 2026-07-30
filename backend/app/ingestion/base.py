import datetime
from dataclasses import dataclass
from typing import Protocol


@dataclass
class DailySummary:
    date: datetime.date
    steps_total: int | None = None
    calories_total: int | None = None
    resting_heart_rate: int | None = None
    hrv_rmssd_avg: float | None = None
    spo2_avg: float | None = None
    sleep_duration_minutes: int | None = None
    sleep_efficiency: int | None = None
    active_minutes: int | None = None
    raw_payload: dict | None = None


class WearableClient(Protocol):
    async def fetch_daily_summary(self, date: datetime.date) -> DailySummary: ...
