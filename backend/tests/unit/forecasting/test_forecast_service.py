import datetime

import pytest

from app.config import get_settings
from app.forecasting import forecast_service
from app.forecasting.model import FEATURE_COLUMNS, MODEL_CANDIDATES
from app.storage.repositories.forecast_run_repository import ForecastRunRepository
from app.storage.repositories.metrics_repository import MetricsRepository

PROVIDER = "google_health"


async def _seed_consecutive_days(session, n_days: int, start: datetime.date) -> datetime.date:
    repo = MetricsRepository(session)
    last_date = start
    for i in range(n_days):
        date = start + datetime.timedelta(days=i)
        last_date = date
        await repo.upsert_daily(
            date=date,
            provider=PROVIDER,
            hrv_rmssd_avg=40 + (i % 5),
            resting_heart_rate=60 - (i % 3),
            sleep_efficiency=85 + (i % 4),
            readiness_score=50 + (i % 6),
        )
    return last_date


async def test_train_and_evaluate_persists_run_and_model(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "model_dir", str(tmp_path))
    await _seed_consecutive_days(db_session, n_days=25, start=datetime.date(2026, 3, 1))

    result = await forecast_service.train_and_evaluate(db_session)

    assert result.winning_model in MODEL_CANDIDATES
    assert len(result.candidates) == 3
    assert result.winner.n_samples == 24  # 25 days -> 24 targets with a usable predecessor
    assert result.winner.n_test_folds == 4  # default min_train_size=20
    assert result.winner.model_mae is not None
    assert result.winner.baseline_mae is not None

    latest_run = await ForecastRunRepository(db_session).get_latest()
    assert latest_run is not None
    assert latest_run.target_metric == "readiness_score"
    assert latest_run.winning_model == result.winning_model
    assert latest_run.n_samples == 24
    assert set(latest_run.candidate_results) == set(MODEL_CANDIDATES)

    assert (tmp_path / "readiness_forecast.joblib").exists()


async def test_get_feature_importance_covers_all_features(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "model_dir", str(tmp_path))
    await _seed_consecutive_days(db_session, n_days=25, start=datetime.date(2026, 5, 1))
    train_result = await forecast_service.train_and_evaluate(db_session)

    result = await forecast_service.get_feature_importance(db_session)

    assert result is not None
    assert result.model_name == train_result.winning_model
    assert {feature for feature, _ in result.importances} == set(FEATURE_COLUMNS)
    assert sum(pct for _, pct in result.importances) == pytest.approx(100.0, abs=0.5)


async def test_get_feature_importance_returns_none_before_training(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "model_dir", str(tmp_path))
    result = await forecast_service.get_feature_importance(db_session)
    assert result is None


async def test_get_prediction_uses_latest_day_as_lag_input(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "model_dir", str(tmp_path))
    last_date = await _seed_consecutive_days(db_session, n_days=25, start=datetime.date(2026, 4, 1))

    await forecast_service.train_and_evaluate(db_session)
    prediction = await forecast_service.get_prediction(db_session)

    assert prediction is not None
    assert prediction.last_actual_date == last_date
    assert prediction.predicted_date == last_date + datetime.timedelta(days=1)
    assert 0.0 <= prediction.predicted_readiness <= 100.0


async def test_get_prediction_returns_none_before_training(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "model_dir", str(tmp_path))
    prediction = await forecast_service.get_prediction(db_session)
    assert prediction is None
