import pandas as pd
import pytest

from app.forecasting.evaluation import compare_models, walk_forward_validate
from app.forecasting.model import FEATURE_COLUMNS, MODEL_CANDIDATES

OFFSET = 3.0


def _synthetic_df(n_rows: int) -> pd.DataFrame:
    # readiness_score is always readiness_score_lag1 + a constant offset, so the naive
    # baseline's absolute error (|lag1 - actual|) is exactly OFFSET on every test fold,
    # regardless of how the Ridge model itself behaves - a hand-verifiable baseline MAE.
    rows = []
    for i in range(n_rows):
        lag1 = 50 + i
        rows.append(
            {
                "hrv_rmssd_avg_lag1": 40 + i,
                "resting_heart_rate_lag1": 60 - i * 0.1,
                "sleep_efficiency_lag1": 85,
                "readiness_score_lag1": lag1,
                "readiness_score": lag1 + OFFSET,
            }
        )
    return pd.DataFrame(rows)


async def test_walk_forward_validate_hand_verified_baseline():
    df = _synthetic_df(25)
    result = walk_forward_validate(df, MODEL_CANDIDATES["ridge"], min_train_size=20)

    assert result.n_samples == 25
    assert result.n_test_folds == 5
    assert result.baseline_mae == pytest.approx(OFFSET)
    assert result.model_mae is not None and result.model_mae >= 0
    assert result.improvement_pct is not None


async def test_walk_forward_validate_insufficient_data():
    df = _synthetic_df(10)
    result = walk_forward_validate(df, MODEL_CANDIDATES["ridge"], min_train_size=20)

    assert result.n_samples == 10
    assert result.n_test_folds == 0
    assert result.model_mae is None
    assert result.baseline_mae is None
    assert result.improvement_pct is None


async def test_compare_models_evaluates_all_candidates_with_same_baseline():
    df = _synthetic_df(25)
    results = compare_models(df, min_train_size=20)

    assert set(results) == set(MODEL_CANDIDATES)
    for result in results.values():
        assert result.n_samples == 25
        assert result.n_test_folds == 5
        # the naive baseline doesn't depend on which model is being compared
        assert result.baseline_mae == pytest.approx(OFFSET)


def test_all_candidates_fit_and_predict_without_error():
    df = _synthetic_df(25)
    for factory in MODEL_CANDIDATES.values():
        pipeline = factory()
        pipeline.fit(df[FEATURE_COLUMNS], df["readiness_score"])
        prediction = pipeline.predict(df[FEATURE_COLUMNS].iloc[[0]])
        assert len(prediction) == 1
