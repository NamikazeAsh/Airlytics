import datetime

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

BASE_URL = "https://health.googleapis.com/v4"


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504)


def _civil_date(date: datetime.date) -> dict:
    return {"year": date.year, "month": date.month, "day": date.day}


def _civil_time_interval(start_date: datetime.date, end_date: datetime.date) -> dict:
    return {
        "start": {"date": _civil_date(start_date)},
        "end": {"date": _civil_date(end_date)},
    }


def _field_name(data_type: str) -> str:
    return data_type.replace("-", "_")


def daily_summary_date_filter(data_type: str, date: datetime.date) -> str:
    next_date = date + datetime.timedelta(days=1)
    field = _field_name(data_type)
    return f'{field}.date >= "{date.isoformat()}" AND {field}.date < "{next_date.isoformat()}"'


def session_civil_start_filter(data_type: str, date: datetime.date) -> str:
    next_date = date + datetime.timedelta(days=1)
    field = _field_name(data_type)
    return f'{field}.interval.civil_start_time >= "{date.isoformat()}" AND {field}.interval.civil_start_time < "{next_date.isoformat()}"'


def sleep_civil_end_filter(date: datetime.date) -> str:
    next_date = date + datetime.timedelta(days=1)
    return f'sleep.interval.civil_end_time >= "{date.isoformat()}" AND sleep.interval.civil_end_time < "{next_date.isoformat()}"'


class GoogleHealthClient:
    def __init__(self, access_token: str):
        self._access_token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    @retry(retry=retry_if_exception(_is_retryable), stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
    async def daily_rollup(self, data_type: str, start_date: datetime.date, end_date: datetime.date) -> dict:
        url = f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"
        body = {"range": _civil_time_interval(start_date, end_date), "windowSizeDays": 1}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=body, headers=self._headers())
            response.raise_for_status()
        return response.json()

    @retry(retry=retry_if_exception(_is_retryable), stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
    async def reconcile(self, data_type: str, filter_expr: str) -> dict:
        url = f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:reconcile"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"filter": filter_expr}, headers=self._headers())
            response.raise_for_status()
        return response.json()
