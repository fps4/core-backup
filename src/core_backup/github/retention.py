from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

LOG = logging.getLogger(__name__)


def enforce_retention(base_path: Path, retention_days: int) -> None:
    if retention_days <= 0:
        return

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    if not base_path.exists():
        return

    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        try:
            dir_date = datetime.strptime(child.name, "%Y-%m-%d")
        except ValueError:
            LOG.debug("Skipping non-date directory %s", child)
            continue

        if dir_date < cutoff:
            LOG.info("Removing expired backup %s", child)
            _remove_path(child)


def _remove_path(path: Path) -> None:
    for sub in path.glob("*"):
        if sub.is_dir():
            _remove_path(sub)
        else:
            sub.unlink(missing_ok=True)
    path.rmdir()
