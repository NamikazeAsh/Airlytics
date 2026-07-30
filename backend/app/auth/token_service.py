import asyncio
import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import oauth_client
from app.core.security import decrypt, encrypt
from app.storage.repositories.token_repository import TokenRepository

PROVIDER = "google_health"
REFRESH_BUFFER = datetime.timedelta(minutes=5)

_refresh_lock = asyncio.Lock()


class NotConnectedError(Exception):
    pass


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


async def get_valid_access_token(session: AsyncSession) -> str:
    repo = TokenRepository(session)
    token = await repo.get(PROVIDER)
    if token is None:
        raise NotConnectedError("No Google Health API connection for this account")

    if token.expires_at - _now() > REFRESH_BUFFER:
        return decrypt(token.access_token_encrypted)

    async with _refresh_lock:
        token = await repo.get(PROVIDER)
        if token.expires_at - _now() > REFRESH_BUFFER:
            return decrypt(token.access_token_encrypted)

        current_refresh_token = decrypt(token.refresh_token_encrypted)
        refreshed = await oauth_client.refresh_access_token(current_refresh_token)
        new_refresh_token = refreshed.refresh_token or current_refresh_token

        await repo.upsert(
            provider=PROVIDER,
            access_token_encrypted=encrypt(refreshed.access_token),
            refresh_token_encrypted=encrypt(new_refresh_token),
            scope=token.scope,
            expires_at=refreshed.expires_at,
            external_user_id=token.external_user_id,
        )
        return refreshed.access_token
