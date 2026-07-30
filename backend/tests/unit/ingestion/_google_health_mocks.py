import respx
from httpx import Response

from app.ingestion.providers.google_health.client import BASE_URL

EMPTY_ROLLUP = {"rollupDataPoints": []}
EMPTY_RECONCILE = {"dataPoints": []}


def mock_defaults() -> None:
    for data_type in ("steps", "total-calories", "active-minutes"):
        respx.post(f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp").mock(
            return_value=Response(200, json=EMPTY_ROLLUP)
        )
    for data_type in (
        "daily-resting-heart-rate",
        "daily-heart-rate-variability",
        "daily-oxygen-saturation",
        "sleep",
        "exercise",
    ):
        respx.get(f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:reconcile").mock(
            return_value=Response(200, json=EMPTY_RECONCILE)
        )
