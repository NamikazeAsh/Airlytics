import dataclasses
import datetime

import pandas as pd
from sklearn.inspection import permutation_importance
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import PROVIDER
from app.forecasting.evaluation import EvaluationResult, compare_models
from app.forecasting.feature_builder import TARGET_FIELD, build_dataset, latest_complete_features
from app.forecasting.model import FEATURE_COLUMNS, MODEL_CANDIDATES, fit_candidate, load_model, save_model
from app.storage.repositories.forecast_run_repository import ForecastRunRepository

TARGET_METRIC = "readiness_score"


@dataclasses.dataclass
class PredictionResult:
    predicted_date: datetime.date
    predicted_readiness: float
    last_actual_date: datetime.date
    last_actual_readiness: float


@dataclasses.dataclass
class TrainResult:
    winning_model: str | None
    winner: EvaluationResult
    candidates: dict[str, EvaluationResult]


@dataclasses.dataclass
class FeatureImportanceResult:
    model_name: str
    importances: list[tuple[str, float]]


async def train_and_evaluate(session: AsyncSession) -> TrainResult:
    df = await build_dataset(session, PROVIDER)
    candidates = compare_models(df)

    scored = {name: r for name, r in candidates.items() if r.model_mae is not None}
    winning_model = min(scored, key=lambda name: scored[name].model_mae) if scored else None
    winner = candidates[winning_model] if winning_model else next(iter(candidates.values()))

    if winning_model is not None:
        pipeline = fit_candidate(MODEL_CANDIDATES[winning_model], df)
        save_model(pipeline)

    await ForecastRunRepository(session).create(
        target_metric=TARGET_METRIC,
        winning_model=winning_model,
        n_samples=winner.n_samples,
        n_test_folds=winner.n_test_folds,
        model_mae=winner.model_mae,
        baseline_mae=winner.baseline_mae,
        improvement_pct=winner.improvement_pct,
        candidate_results={name: dataclasses.asdict(r) for name, r in candidates.items()},
    )
    return TrainResult(winning_model=winning_model, winner=winner, candidates=candidates)


async def get_prediction(session: AsyncSession) -> PredictionResult | None:
    pipeline = load_model()
    if pipeline is None:
        return None

    latest = await latest_complete_features(session, PROVIDER)
    if latest is None:
        return None
    last_actual_date, features = latest

    row = pd.DataFrame([features])[FEATURE_COLUMNS]
    predicted = float(pipeline.predict(row)[0])
    predicted = max(0.0, min(100.0, predicted))

    return PredictionResult(
        predicted_date=last_actual_date + datetime.timedelta(days=1),
        predicted_readiness=round(predicted, 1),
        last_actual_date=last_actual_date,
        last_actual_readiness=features[f"{TARGET_FIELD}_lag1"],
    )


async def get_feature_importance(session: AsyncSession) -> FeatureImportanceResult | None:
    pipeline = load_model()
    if pipeline is None:
        return None

    latest_run = await ForecastRunRepository(session).get_latest()
    if latest_run is None or latest_run.winning_model is None:
        return None

    df = await build_dataset(session, PROVIDER)
    if df.empty:
        return None

    result = permutation_importance(
        pipeline, df[FEATURE_COLUMNS], df[TARGET_FIELD], n_repeats=10, random_state=0
    )
    raw = {feature: max(0.0, score) for feature, score in zip(FEATURE_COLUMNS, result.importances_mean)}
    total = sum(raw.values())
    normalized = {feature: (score / total * 100 if total else 0.0) for feature, score in raw.items()}
    importances = sorted(normalized.items(), key=lambda pair: pair[1], reverse=True)

    return FeatureImportanceResult(model_name=latest_run.winning_model, importances=importances)
