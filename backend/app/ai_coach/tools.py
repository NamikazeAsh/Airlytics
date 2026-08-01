import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_coach.llm_client import ToolSpec
from app.analytics.readiness import READINESS_WEIGHTS
from app.analytics.service import METRICS, AnalyticsService
from app.auth.token_service import PROVIDER
from app.forecasting.forecast_service import get_feature_importance

_DATE_PARAM = {"type": "string", "format": "date", "description": "ISO date, YYYY-MM-DD"}

TOOL_SPECS = [
    ToolSpec(
        name="get_metric_series",
        description="Get the daily values of a health metric over a date range.",
        parameters={
            "type": "object",
            "properties": {"metric": {"type": "string", "enum": METRICS}, "start": _DATE_PARAM, "end": _DATE_PARAM},
            "required": ["metric", "start", "end"],
        },
    ),
    ToolSpec(
        name="get_rolling_average",
        description="Get the rolling average of a metric over the last N days.",
        parameters={
            "type": "object",
            "properties": {"metric": {"type": "string", "enum": METRICS}, "window_days": {"type": "integer"}},
            "required": ["metric", "window_days"],
        },
    ),
    ToolSpec(
        name="get_trend",
        description="Get the trend direction and percent change of a metric over a date range.",
        parameters={
            "type": "object",
            "properties": {"metric": {"type": "string", "enum": METRICS}, "start": _DATE_PARAM, "end": _DATE_PARAM},
            "required": ["metric", "start", "end"],
        },
    ),
    ToolSpec(
        name="get_anomalies",
        description="Get days where any metric deviated significantly from the user's personal baseline.",
        parameters={
            "type": "object",
            "properties": {"start": _DATE_PARAM, "end": _DATE_PARAM},
            "required": ["start", "end"],
        },
    ),
    ToolSpec(
        name="compare_periods",
        description="Compare the average of a metric between two date ranges.",
        parameters={
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": METRICS},
                "period_a_start": _DATE_PARAM,
                "period_a_end": _DATE_PARAM,
                "period_b_start": _DATE_PARAM,
                "period_b_end": _DATE_PARAM,
            },
            "required": ["metric", "period_a_start", "period_a_end", "period_b_start", "period_b_end"],
        },
    ),
    ToolSpec(
        name="get_readiness_explanation",
        description=(
            "Explain what's driving the readiness score on a specific date, broken down by how far "
            "HRV, resting heart rate, and sleep efficiency deviated from personal baseline that day."
        ),
        parameters={"type": "object", "properties": {"date": _DATE_PARAM}, "required": ["date"]},
    ),
    ToolSpec(
        name="get_readiness_drivers",
        description=(
            "Get which health metrics most influence the readiness forecasting model's predictions, "
            "based on real feature importance analysis of the trained model - not a guess."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
    ),
]


async def execute_tool(session: AsyncSession, name: str, arguments: dict) -> dict:
    analytics = AnalyticsService(session)

    if name == "get_metric_series":
        rows = await analytics.metrics_repo.get_daily_range(
            provider=PROVIDER,
            start=datetime.date.fromisoformat(arguments["start"]),
            end=datetime.date.fromisoformat(arguments["end"]),
        )
        metric = arguments["metric"]
        return {"series": [{"date": r.date.isoformat(), "value": getattr(r, metric)} for r in rows]}

    if name == "get_rolling_average":
        avg = await analytics.get_rolling_average(PROVIDER, arguments["metric"], arguments["window_days"])
        return {"average": avg}

    if name == "get_trend":
        result = await analytics.get_trend(
            PROVIDER,
            arguments["metric"],
            datetime.date.fromisoformat(arguments["start"]),
            datetime.date.fromisoformat(arguments["end"]),
        )
        return {
            "direction": result.direction,
            "percent_change": result.percent_change,
            "slope_per_day": result.slope_per_day,
            "sample_count": result.sample_count,
        }

    if name == "get_anomalies":
        anomalies = await analytics.get_anomalies(
            PROVIDER, datetime.date.fromisoformat(arguments["start"]), datetime.date.fromisoformat(arguments["end"])
        )
        return {
            "anomalies": [
                {"date": a.date.isoformat(), "metric": a.metric, "value": a.value, "z_score": a.z_score}
                for a in anomalies
            ]
        }

    if name == "compare_periods":
        return await analytics.compare_periods(
            PROVIDER,
            arguments["metric"],
            datetime.date.fromisoformat(arguments["period_a_start"]),
            datetime.date.fromisoformat(arguments["period_a_end"]),
            datetime.date.fromisoformat(arguments["period_b_start"]),
            datetime.date.fromisoformat(arguments["period_b_end"]),
        )

    if name == "get_readiness_explanation":
        date = datetime.date.fromisoformat(arguments["date"])
        breakdown = {metric: await analytics.get_zscore(PROVIDER, metric, date) for metric in READINESS_WEIGHTS}
        rows = await analytics.metrics_repo.get_daily_range(provider=PROVIDER, start=date, end=date)
        score = rows[0].readiness_score if rows else None
        return {"date": date.isoformat(), "readiness_score": score, "baseline_deviation_z_scores": breakdown}

    if name == "get_readiness_drivers":
        result = await get_feature_importance(session)
        if result is None:
            return {"error": "No forecasting model has been trained yet."}
        return {
            "model_name": result.model_name,
            "drivers": [{"feature": feature, "importance_pct": round(pct, 2)} for feature, pct in result.importances],
        }

    raise ValueError(f"Unknown tool '{name}'")
