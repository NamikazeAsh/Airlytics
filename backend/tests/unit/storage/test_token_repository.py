import datetime

from app.storage.repositories.token_repository import TokenRepository


async def test_upsert_then_get(db_session):
    repo = TokenRepository(db_session)
    expires_at = datetime.datetime(2026, 1, 1)

    await repo.upsert(
        provider="fitbit",
        access_token_encrypted=b"access-1",
        refresh_token_encrypted=b"refresh-1",
        scope="activity heartrate",
        expires_at=expires_at,
        external_user_id="user-1",
    )

    token = await repo.get("fitbit")
    assert token is not None
    assert token.access_token_encrypted == b"access-1"
    assert token.expires_at == expires_at


async def test_upsert_overwrites_existing(db_session):
    repo = TokenRepository(db_session)
    expires_at = datetime.datetime(2026, 1, 1)

    await repo.upsert(
        provider="fitbit",
        access_token_encrypted=b"access-1",
        refresh_token_encrypted=b"refresh-1",
        scope="activity",
        expires_at=expires_at,
        external_user_id="user-1",
    )
    await repo.upsert(
        provider="fitbit",
        access_token_encrypted=b"access-2",
        refresh_token_encrypted=b"refresh-2",
        scope="activity heartrate sleep",
        expires_at=expires_at,
        external_user_id="user-1",
    )

    token = await repo.get("fitbit")
    assert token.access_token_encrypted == b"access-2"
    assert token.refresh_token_encrypted == b"refresh-2"
    assert token.scope == "activity heartrate sleep"


async def test_get_missing_provider_returns_none(db_session):
    repo = TokenRepository(db_session)
    assert await repo.get("oura") is None
