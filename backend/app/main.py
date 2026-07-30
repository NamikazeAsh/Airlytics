from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routers.analytics import router as analytics_router
from app.api.routers.coach import router as coach_router
from app.api.routers.metrics import router as metrics_router
from app.api.routers.sync import router as sync_router
from app.auth.router import router as auth_router
from app.core.scheduler import scheduler
from app.ingestion.scheduler_jobs import register_jobs

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_jobs()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Airlytics", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(sync_router)
app.include_router(metrics_router)
app.include_router(analytics_router)
app.include_router(coach_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
