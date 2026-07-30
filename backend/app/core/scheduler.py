from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

# APScheduler's SQLAlchemyJobStore uses a plain sync engine, unlike the rest
# of the app which uses aiosqlite — strip the async driver from the URL.
_sync_database_url = get_settings().database_url.replace("+aiosqlite", "")

scheduler = AsyncIOScheduler(jobstores={"default": SQLAlchemyJobStore(url=_sync_database_url)})
