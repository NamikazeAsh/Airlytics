import dataclasses

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.forecasting.forecast_service import get_feature_importance, get_prediction, train_and_evaluate
from app.storage.repositories.forecast_run_repository import ForecastRunRepository

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.post("/train")
async def train(session: AsyncSession = Depends(get_session)) -> dict:
    result = await train_and_evaluate(session)
    return {
        "winning_model": result.winning_model,
        "n_samples": result.winner.n_samples,
        "n_test_folds": result.winner.n_test_folds,
        "model_mae": result.winner.model_mae,
        "baseline_mae": result.winner.baseline_mae,
        "improvement_pct": result.winner.improvement_pct,
        "candidate_results": {name: dataclasses.asdict(r) for name, r in result.candidates.items()},
    }


@router.get("/status")
async def status(session: AsyncSession = Depends(get_session)) -> dict | None:
    run = await ForecastRunRepository(session).get_latest()
    if run is None:
        return None
    return {
        "trained_at": run.trained_at.isoformat(),
        "target_metric": run.target_metric,
        "winning_model": run.winning_model,
        "n_samples": run.n_samples,
        "n_test_folds": run.n_test_folds,
        "model_mae": run.model_mae,
        "baseline_mae": run.baseline_mae,
        "improvement_pct": run.improvement_pct,
        "candidate_results": run.candidate_results,
    }


@router.get("/history")
async def history(session: AsyncSession = Depends(get_session)) -> list[dict]:
    runs = await ForecastRunRepository(session).get_recent(limit=20)
    return [
        {
            "trained_at": r.trained_at.isoformat(),
            "winning_model": r.winning_model,
            "model_mae": r.model_mae,
            "baseline_mae": r.baseline_mae,
            "improvement_pct": r.improvement_pct,
            "n_samples": r.n_samples,
        }
        for r in reversed(runs)
    ]


@router.get("/feature-importance")
async def feature_importance(session: AsyncSession = Depends(get_session)) -> dict | None:
    result = await get_feature_importance(session)
    if result is None:
        return None
    return {
        "model_name": result.model_name,
        "importances": [{"feature": feature, "importance_pct": round(pct, 2)} for feature, pct in result.importances],
    }


@router.get("/prediction")
async def prediction(session: AsyncSession = Depends(get_session)) -> dict | None:
    result = await get_prediction(session)
    if result is None:
        return None
    return {
        "predicted_date": result.predicted_date.isoformat(),
        "predicted_readiness": result.predicted_readiness,
        "last_actual_date": result.last_actual_date.isoformat(),
        "last_actual_readiness": result.last_actual_readiness,
    }
