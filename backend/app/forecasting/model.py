from collections.abc import Callable
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import get_settings
from app.forecasting.feature_builder import LAG_FIELDS, TARGET_FIELD

FEATURE_COLUMNS = [f"{field}_lag1" for field in LAG_FIELDS]
MODEL_FILENAME = "readiness_forecast.joblib"

# Three candidates compared under the same walk-forward validation. GradientBoosting is
# deliberately small (shallow trees, few estimators) and included honestly expecting it to
# lose given the small sample size - that comparison is the point, not tuning it to "win".
MODEL_CANDIDATES: dict[str, Callable[[], Pipeline]] = {
    "ridge": lambda: Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))]),
    "elastic_net": lambda: Pipeline(
        [("scaler", StandardScaler()), ("model", ElasticNet(alpha=0.1, l1_ratio=0.5))]
    ),
    "gradient_boosting": lambda: Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", GradientBoostingRegressor(n_estimators=30, max_depth=2, learning_rate=0.1, random_state=0)),
        ]
    ),
}


def _model_path() -> Path:
    return Path(get_settings().model_dir) / MODEL_FILENAME


def fit_candidate(model_factory: Callable[[], Pipeline], df: pd.DataFrame) -> Pipeline:
    pipeline = model_factory()
    pipeline.fit(df[FEATURE_COLUMNS], df[TARGET_FIELD])
    return pipeline


def save_model(pipeline: Pipeline) -> None:
    path = _model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)


def load_model() -> Pipeline | None:
    path = _model_path()
    if not path.exists():
        return None
    return joblib.load(path)
