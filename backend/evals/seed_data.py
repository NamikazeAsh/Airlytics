import datetime
import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.readiness import update_readiness_for_date
from app.auth.token_service import PROVIDER
from app.storage.repositories.metrics_repository import MetricsRepository

# Deterministic synthetic history, always ending "today" so the eval stays valid whenever
# it's run. A slow HRV/RHR/steps trend plus one deliberate HRV dip gives the trend- and
# anomaly-related eval cases a real, checkable answer instead of flat noise.
DAYS = 90
ANOMALY_DAYS_AGO = 5


def anomaly_date() -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=ANOMALY_DAYS_AGO)


async def seed_synthetic_data(session: AsyncSession) -> None:
    repo = MetricsRepository(session)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=DAYS - 1)
    dates = [start + datetime.timedelta(days=i) for i in range(DAYS)]

    for i, date in enumerate(dates):
        wave = math.sin(i / 5)

        hrv = 42 + i * 0.05 + wave * 2
        if date == anomaly_date():
            hrv -= 15  # deliberate anomaly dip

        await repo.upsert_daily(
            date=date,
            provider=PROVIDER,
            hrv_rmssd_avg=round(hrv, 1),
            resting_heart_rate=round(62 - i * 0.03 + wave * 1.5),
            sleep_efficiency=round(86 + wave * 2),
            steps_total=round(7500 + i * 15 + wave * 400),
            active_minutes=round(35 + wave * 8),
            calories_total=round(2200 + wave * 100),
            spo2_avg=round(96.5 + wave * 0.3, 1),
        )

    # Compute readiness the same way the app does in production (nightly_rollups_job),
    # so the eval's readiness numbers are internally consistent with the real formula.
    for date in dates:
        await update_readiness_for_date(session, PROVIDER, date)
