import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import SyncState


class SyncStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, provider: str, metric_type: str) -> SyncState | None:
        return await self.session.get(SyncState, (provider, metric_type))

    async def get_all_for_provider(self, provider: str) -> list[SyncState]:
        result = await self.session.execute(select(SyncState).where(SyncState.provider == provider))
        return list(result.scalars())

    async def upsert(
        self,
        provider: str,
        metric_type: str,
        status: str,
        last_synced_date: datetime.date | None = None,
        last_synced_at: datetime.datetime | None = None,
        last_error: str | None = None,
        cursor: dict | None = None,
    ) -> None:
        stmt = insert(SyncState).values(
            provider=provider,
            metric_type=metric_type,
            status=status,
            last_synced_date=last_synced_date,
            last_synced_at=last_synced_at,
            last_error=last_error,
            cursor=cursor,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SyncState.provider, SyncState.metric_type],
            set_={
                "status": stmt.excluded.status,
                "last_synced_date": stmt.excluded.last_synced_date,
                "last_synced_at": stmt.excluded.last_synced_at,
                "last_error": stmt.excluded.last_error,
                "cursor": stmt.excluded.cursor,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        self.session.expire_all()
