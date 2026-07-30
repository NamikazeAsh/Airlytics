import datetime

from app.ai_coach import insights_service
from app.ai_coach.llm_client import LLMResponse
from app.auth.token_service import PROVIDER
from app.storage.repositories.insight_repository import InsightRepository
from app.storage.repositories.metrics_repository import MetricsRepository


class FakeLLMClient:
    def __init__(self, content: str):
        self._content = content

    async def generate(self, *, system, messages, tools=None):
        return LLMResponse(content=self._content, tool_calls=[])


async def test_generate_insights_returns_empty_when_no_signals(db_session, monkeypatch):
    def _fail_if_called():
        raise AssertionError("LLM should not be called when there are no signals")

    monkeypatch.setattr(insights_service, "get_llm_client", _fail_if_called)
    result = await insights_service.generate_insights(db_session)
    assert result == []


async def test_generate_insights_persists_lines_from_llm(db_session, monkeypatch):
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(6)]
    repo = MetricsRepository(db_session)
    for i, d in enumerate(days):
        await repo.upsert_daily(date=d, provider=PROVIDER, steps_total=1000 + i * 200)

    monkeypatch.setattr(
        insights_service,
        "get_llm_client",
        lambda: FakeLLMClient("Your steps have been climbing steadily.\nYour activity is more consistent lately."),
    )

    result = await insights_service.generate_insights(db_session)

    assert result == ["Your steps have been climbing steadily.", "Your activity is more consistent lately."]

    stored = await InsightRepository(db_session).get_since(today - datetime.timedelta(days=1))
    assert len(stored) == 2
