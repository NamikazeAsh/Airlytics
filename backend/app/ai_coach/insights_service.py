import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_coach.llm_client import Message
from app.ai_coach.provider_factory import get_llm_client
from app.analytics.service import AnalyticsService
from app.auth.token_service import PROVIDER
from app.storage.repositories.insight_repository import InsightRepository

INSIGHT_METRICS = ["steps_total", "resting_heart_rate", "hrv_rmssd_avg", "sleep_efficiency", "readiness_score"]

SYSTEM_PROMPT = """You generate short, evidence-based health insight cards from structured trend and anomaly data.
Each insight must cite the actual numbers provided below. Never invent data. Keep each insight to 1-2 sentences.
Return each insight on its own line, with no numbering and no extra commentary."""


async def generate_insights(session: AsyncSession) -> list[str]:
    analytics = AnalyticsService(session)
    today = datetime.date.today()

    signals = []
    for metric in INSIGHT_METRICS:
        trend = await analytics.get_trend(PROVIDER, metric, today - datetime.timedelta(days=30), today)
        if trend.direction != "insufficient_data":
            signals.append(f"{metric}: {trend.direction} ({trend.percent_change}% over 30d)")

    anomalies = await analytics.get_anomalies(PROVIDER, today - datetime.timedelta(days=7), today)
    for a in anomalies:
        signals.append(f"{a.date.isoformat()}: {a.metric} anomaly, value {a.value} (z={a.z_score})")

    if not signals:
        return []

    llm = get_llm_client()
    user_message = (
        "Here is the last 30 days of trend and anomaly data:\n"
        + "\n".join(signals)
        + "\n\nGenerate 2-3 proactive insights."
    )
    response = await llm.generate(system=SYSTEM_PROMPT, messages=[Message(role="user", content=user_message)])
    insight_texts = [line.strip() for line in (response.content or "").split("\n") if line.strip()]

    repo = InsightRepository(session)
    for text in insight_texts:
        await repo.create(category="trend", body=text)

    return insight_texts
