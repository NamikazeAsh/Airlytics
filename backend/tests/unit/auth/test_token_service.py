import datetime

import pytest
import respx
from httpx import Response

from app.auth import oauth_client, token_service
from app.core.security import decrypt, encrypt
from app.storage.repositories.token_repository import TokenRepository


async def test_raises_when_not_connected(db_session):
    with pytest.raises(token_service.NotConnectedError):
        await token_service.get_valid_access_token(db_session)


@respx.mock
async def test_returns_cached_token_without_refreshing(db_session):
    repo = TokenRepository(db_session)
    far_future = token_service._now() + datetime.timedelta(hours=1)
    await repo.upsert(
        provider=token_service.PROVIDER,
        access_token_encrypted=encrypt("still-valid-access-token"),
        refresh_token_encrypted=encrypt("refresh-token"),
        scope="activity_and_fitness.readonly",
        expires_at=far_future,
        external_user_id="me",
    )

    access_token = await token_service.get_valid_access_token(db_session)

    assert access_token == "still-valid-access-token"


@respx.mock
async def test_refreshes_when_close_to_expiry(db_session):
    respx.post(oauth_client.TOKEN_URL).mock(
        return_value=Response(200, json={"access_token": "refreshed-access-token", "expires_in": 3600})
    )
    repo = TokenRepository(db_session)
    almost_expired = token_service._now() + datetime.timedelta(minutes=1)
    await repo.upsert(
        provider=token_service.PROVIDER,
        access_token_encrypted=encrypt("stale-access-token"),
        refresh_token_encrypted=encrypt("refresh-token"),
        scope="activity_and_fitness.readonly",
        expires_at=almost_expired,
        external_user_id="me",
    )

    access_token = await token_service.get_valid_access_token(db_session)

    assert access_token == "refreshed-access-token"
    stored = await repo.get(token_service.PROVIDER)
    assert decrypt(stored.access_token_encrypted) == "refreshed-access-token"
    assert decrypt(stored.refresh_token_encrypted) == "refresh-token"
