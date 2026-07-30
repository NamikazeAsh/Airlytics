import datetime

from app.ai_coach.context_builder import build_system_prompt
from app.auth.token_service import PROVIDER
from app.storage.repositories.metrics_repository import MetricsRepository


async def test_build_system_prompt_includes_recent_averages(db_session):
    today = datetime.date.today()
    repo = MetricsRepository(db_session)
    await repo.upsert_daily(date=today, provider=PROVIDER, steps_total=8000)

    prompt = await build_system_prompt(db_session)

    assert "Airlytics" in prompt
    assert "steps_total" in prompt
    assert "No anomalies flagged" in prompt


async def test_build_system_prompt_handles_no_data(db_session):
    prompt = await build_system_prompt(db_session)
    assert "Recent state of the union" in prompt
