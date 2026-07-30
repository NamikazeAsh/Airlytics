import datetime
import shutil
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "airlytics.db"
BACKUP_DIR = Path(__file__).resolve().parent.parent / "data" / "backups"


def backup() -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"airlytics_{timestamp}.db"
    shutil.copy(DB_PATH, dest)
    return dest


if __name__ == "__main__":
    print(f"Backed up to {backup()}")
