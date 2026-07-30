import datetime

from app.storage.repositories.insight_repository import InsightRepository


async def test_create_and_get_since(db_session):
    repo = InsightRepository(db_session)
    await repo.create(category="trend", body="Your steps rose 20% this week.")

    since = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=1)
    rows = await repo.get_since(since)
    assert len(rows) == 1
    assert rows[0].body == "Your steps rose 20% this week."


async def test_get_since_excludes_older_insights(db_session):
    repo = InsightRepository(db_session)
    await repo.create(category="trend", body="old insight")

    future_cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(days=1)
    rows = await repo.get_since(future_cutoff)
    assert rows == []
