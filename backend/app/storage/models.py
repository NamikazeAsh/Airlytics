import datetime

from sqlalchemy import JSON, Date, DateTime, Float, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# SQLite's DateTime type drops tzinfo on round-trip, so every stored datetime
# here is naive UTC by convention. Always pass/compare naive UTC values.


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    scope: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    external_user_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), primary_key=True)

    steps_total: Mapped[int | None] = mapped_column(default=None)
    calories_total: Mapped[int | None] = mapped_column(default=None)
    calories_bmr: Mapped[int | None] = mapped_column(default=None)
    resting_heart_rate: Mapped[int | None] = mapped_column(default=None)
    hrv_rmssd_avg: Mapped[float | None] = mapped_column(Float, default=None)
    spo2_avg: Mapped[float | None] = mapped_column(Float, default=None)
    spo2_min: Mapped[float | None] = mapped_column(Float, default=None)
    sleep_duration_minutes: Mapped[int | None] = mapped_column(default=None)
    sleep_efficiency: Mapped[int | None] = mapped_column(default=None)
    readiness_score: Mapped[float | None] = mapped_column(Float, default=None)
    readiness_source: Mapped[str | None] = mapped_column(String(30), default=None)
    active_minutes: Mapped[int | None] = mapped_column(default=None)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class SleepLog(Base):
    __tablename__ = "sleep_logs"

    external_log_id: Mapped[str] = mapped_column(String(300), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    date: Mapped[datetime.date] = mapped_column(Date)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int | None] = mapped_column(default=None)
    efficiency: Mapped[int | None] = mapped_column(default=None)
    stages: Mapped[dict | None] = mapped_column(JSON, default=None)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    external_activity_id: Mapped[str] = mapped_column(String(300), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    date: Mapped[datetime.date] = mapped_column(Date)
    activity_type: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int | None] = mapped_column(default=None)
    calories: Mapped[int | None] = mapped_column(default=None)
    avg_heart_rate: Mapped[int | None] = mapped_column(default=None)
    distance_km: Mapped[float | None] = mapped_column(Float, default=None)


class PeriodSummary(Base):
    __tablename__ = "period_summaries"

    period_start: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    period_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    metric: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))

    avg_value: Mapped[float | None] = mapped_column(Float, default=None)
    min_value: Mapped[float | None] = mapped_column(Float, default=None)
    max_value: Mapped[float | None] = mapped_column(Float, default=None)
    stddev_value: Mapped[float | None] = mapped_column(Float, default=None)
    trend_slope: Mapped[float | None] = mapped_column(Float, default=None)
    sample_count: Mapped[int] = mapped_column(default=0)

    computed_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now)


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now)


class AiMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(default=None)
    tool_calls: Mapped[list | None] = mapped_column(JSON, default=None)
    tool_call_id: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now)


class AiInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utc_now)
    category: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column()
    acknowledged: Mapped[bool] = mapped_column(default=False)


class SyncState(Base):
    __tablename__ = "sync_state"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    metric_type: Mapped[str] = mapped_column(String(50), primary_key=True)

    last_synced_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    last_synced_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=None)
    status: Mapped[str] = mapped_column(String(20), default="idle")
    last_error: Mapped[str | None] = mapped_column(default=None)
    cursor: Mapped[dict | None] = mapped_column(JSON, default=None)
