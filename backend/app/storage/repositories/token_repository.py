import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import OAuthToken


class TokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, provider: str) -> OAuthToken | None:
        return await self.session.get(OAuthToken, provider)

    async def upsert(
        self,
        provider: str,
        access_token_encrypted: bytes,
        refresh_token_encrypted: bytes,
        scope: str,
        expires_at: datetime.datetime,
        external_user_id: str,
    ) -> None:
        stmt = insert(OAuthToken).values(
            provider=provider,
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            scope=scope,
            expires_at=expires_at,
            external_user_id=external_user_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[OAuthToken.provider],
            set_={
                "access_token_encrypted": stmt.excluded.access_token_encrypted,
                "refresh_token_encrypted": stmt.excluded.refresh_token_encrypted,
                "scope": stmt.excluded.scope,
                "expires_at": stmt.excluded.expires_at,
                "external_user_id": stmt.excluded.external_user_id,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        self.session.expire_all()

    async def delete(self, provider: str) -> None:
        await self.session.execute(delete(OAuthToken).where(OAuthToken.provider == provider))
        await self.session.commit()
        self.session.expire_all()
