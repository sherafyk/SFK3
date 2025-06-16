from datetime import datetime, timedelta
from pathlib import Path

from backend.utils import UPLOAD_FOLDER

UPLOAD_DIR = Path(UPLOAD_FOLDER)


def purge_old_uploads(days: int = 7) -> None:
    """Delete files in ``UPLOAD_DIR`` older than ``days`` days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    for p in UPLOAD_DIR.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff.timestamp():
                p.unlink(missing_ok=True)
        except FileNotFoundError:
            # File might be removed between listing and deletion
            pass
