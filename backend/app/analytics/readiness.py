import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import AnalyticsService
from app.storage.repositories.metrics_repository import MetricsRepository

# Positive weight: higher-than-baseline is good. Negative weight: lower-than-baseline is good.
READINESS_WEIGHTS = {
    "hrv_rmssd_avg": 0.4,
    "resting_heart_rate": -0.3,
    "sleep_efficiency": 0.3,
}

READINESS_SOURCE = "computed_fallback"


async def compute_readiness_score(
    session: AsyncSession, provider: str, date: datetime.date, baseline_days: int = 30
) -> float | None:
    analytics = AnalyticsService(session)
    weighted_sum = 0.0
    total_weight = 0.0

    for metric, weight in READINESS_WEIGHTS.items():
        z = await analytics.get_zscore(provider, metric, date, baseline_days)
        if z is None:
            continue
        weighted_sum += weight * z
        total_weight += abs(weight)

    if total_weight == 0:
        return None

    normalized_z = weighted_sum / total_weight
    score = 50 + normalized_z * 15
    return round(max(0.0, min(100.0, score)), 1)


async def update_readiness_for_date(session: AsyncSession, provider: str, date: datetime.date) -> float | None:
    score = await compute_readiness_score(session, provider, date)
    if score is None:
        return None
    await MetricsRepository(session).upsert_daily(
        date=date, provider=provider, readiness_score=score, readiness_source=READINESS_SOURCE
    )
    return score
