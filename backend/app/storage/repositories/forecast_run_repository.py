from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import ForecastRun


class ForecastRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        target_metric: str,
        n_samples: int,
        n_test_folds: int,
        model_mae: float | None,
        baseline_mae: float | None,
        improvement_pct: float | None,
        winning_model: str | None = None,
        candidate_results: dict | None = None,
    ) -> None:
        self.session.add(
            ForecastRun(
                target_metric=target_metric,
                winning_model=winning_model,
                n_samples=n_samples,
                n_test_folds=n_test_folds,
                model_mae=model_mae,
                baseline_mae=baseline_mae,
                improvement_pct=improvement_pct,
                candidate_results=candidate_results,
            )
        )
        await self.session.commit()

    async def get_latest(self) -> ForecastRun | None:
        stmt = select(ForecastRun).order_by(ForecastRun.trained_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_recent(self, limit: int = 20) -> list[ForecastRun]:
        stmt = select(ForecastRun).order_by(ForecastRun.trained_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars())
