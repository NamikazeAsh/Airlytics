import dataclasses


@dataclasses.dataclass
class SyncProgress:
    status: str = "idle"  # idle | running | done | error
    stage: str = ""  # "syncing" | "computing_readiness"
    current_day: str | None = None
    day_index: int = 0
    total_days: int = 0
    error: str | None = None


_progress = SyncProgress()


def get_progress() -> SyncProgress:
    return _progress


def update_progress(**fields) -> None:
    global _progress
    _progress = dataclasses.replace(_progress, **fields)


def reset_progress() -> None:
    global _progress
    _progress = SyncProgress()
