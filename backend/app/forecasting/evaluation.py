import dataclasses
from collections.abc import Callable

import pandas as pd
from sklearn.pipeline import Pipeline

from app.forecasting.feature_builder import TARGET_FIELD
from app.forecasting.model import FEATURE_COLUMNS, MODEL_CANDIDATES, fit_candidate

BASELINE_COLUMN = "readiness_score_lag1"


@dataclasses.dataclass
class EvaluationResult:
    model_mae: float | None
    baseline_mae: float | None
    improvement_pct: float | None
    n_samples: int
    n_test_folds: int


def walk_forward_validate(
    df: pd.DataFrame, model_factory: Callable[[], Pipeline], min_train_size: int = 20
) -> EvaluationResult:
    n_samples = len(df)
    if n_samples <= min_train_size:
        return EvaluationResult(None, None, None, n_samples, 0)

    model_errors = []
    baseline_errors = []

    for i in range(min_train_size, n_samples):
        train = df.iloc[:i]
        test_row = df.iloc[[i]]

        pipeline = fit_candidate(model_factory, train)
        prediction = pipeline.predict(test_row[FEATURE_COLUMNS])[0]
        actual = test_row[TARGET_FIELD].iloc[0]
        model_errors.append(abs(prediction - actual))

        baseline_prediction = test_row[BASELINE_COLUMN].iloc[0]
        baseline_errors.append(abs(baseline_prediction - actual))

    model_mae = sum(model_errors) / len(model_errors)
    baseline_mae = sum(baseline_errors) / len(baseline_errors)
    improvement_pct = round((baseline_mae - model_mae) / baseline_mae * 100, 2) if baseline_mae else None

    return EvaluationResult(
        model_mae=round(model_mae, 3),
        baseline_mae=round(baseline_mae, 3),
        improvement_pct=improvement_pct,
        n_samples=n_samples,
        n_test_folds=len(model_errors),
    )


def compare_models(df: pd.DataFrame, min_train_size: int = 20) -> dict[str, EvaluationResult]:
    return {name: walk_forward_validate(df, factory, min_train_size) for name, factory in MODEL_CANDIDATES.items()}
