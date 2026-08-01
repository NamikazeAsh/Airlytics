import dataclasses

from evals.seed_data import anomaly_date


@dataclasses.dataclass
class EvalCase:
    id: str
    question: str
    expected_tools: list[str]  # empty means "should NOT call any tool"


def get_eval_cases() -> list[EvalCase]:
    return [
        EvalCase(
            id="rolling_average_steps",
            question="What's my 7-day average step count?",
            expected_tools=["get_rolling_average"],
        ),
        EvalCase(
            id="trend_hrv",
            question="How has my HRV trended over the last 30 days?",
            expected_tools=["get_trend"],
        ),
        EvalCase(
            id="anomalies_this_week",
            question="Have you noticed any anomalies in my health data this week?",
            expected_tools=["get_anomalies"],
        ),
        EvalCase(
            id="compare_resting_hr",
            question="Compare my resting heart rate over the last 30 days to the 30 days before that.",
            expected_tools=["compare_periods"],
        ),
        EvalCase(
            id="readiness_explanation_on_anomaly_day",
            question=f"Why was my readiness score low on {anomaly_date().isoformat()}?",
            expected_tools=["get_readiness_explanation"],
        ),
        EvalCase(
            id="sleep_efficiency_recent",
            question="What has my sleep efficiency looked like recently?",
            expected_tools=["get_rolling_average"],
        ),
        EvalCase(
            id="general_knowledge_no_tool",
            question="What is HRV and why does it matter for recovery?",
            expected_tools=[],
        ),
        EvalCase(
            id="grounding_trap_steps_last_month",
            question="Just give me a quick number: what was my average step count last month?",
            expected_tools=["get_rolling_average"],
        ),
    ]
