import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import AnalyticsService
from app.auth.token_service import PROVIDER

CONTEXT_METRICS = ["steps_total", "resting_heart_rate", "hrv_rmssd_avg", "sleep_efficiency", "readiness_score"]

BASE_INSTRUCTIONS = """You are Airlytics, a personal health coach analyzing the user's own wearable data.
Every number you state must come directly from this system prompt or from a tool result already in this \
conversation. If you have not retrieved a specific figure via a tool call, do not state it — say you don't \
have that number and, if useful, call the right tool to get it instead of estimating or inferring it.
Cite the specific metric and time window you're referencing.
You are not a medical professional; add a brief caveat when giving health-related advice."""


async def build_system_prompt(session: AsyncSession) -> str:
    analytics = AnalyticsService(session)
    today = datetime.date.today()

    lines = [BASE_INSTRUCTIONS, "", "Recent state of the union:"]
    for metric in CONTEXT_METRICS:
        avg_7d = await analytics.get_rolling_average(PROVIDER, metric, 7, today)
        avg_90d = await analytics.get_rolling_average(PROVIDER, metric, 90, today)
        lines.append(f"- {metric}: 7d avg {avg_7d}, 90d avg {avg_90d}")

    anomalies = await analytics.get_anomalies(PROVIDER, today - datetime.timedelta(days=7), today)
    if anomalies:
        lines.append("Active anomalies (last 7 days):")
        for a in anomalies:
            lines.append(f"- {a.date.isoformat()}: {a.metric} = {a.value} (z={a.z_score})")
    else:
        lines.append("No anomalies flagged in the last 7 days.")

    return "\n".join(lines)
