from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Protocol

from .config import JobConfig


class StorageAdapter(Protocol):
    def prepare_run(self, job: JobConfig, started_at: datetime) -> "RunPaths":
        ...

    def enforce_retention(self, job: JobConfig, retention_days: int) -> None:
        ...


@dataclass
class RunPaths:
    root: Path
    metadata_dir: Path


@dataclass
class JobContext:
    job: JobConfig
    started_at: datetime
    storage_paths: RunPaths
    retention_days: int
    workspace: Path


@dataclass
class JobResult:
    job_name: str
    status: str
    started_at: datetime
    completed_at: datetime
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == "success"


class BackupService(Protocol):
    def prepare(self, context: JobContext) -> None:
        ...

    def execute(self, context: JobContext) -> None:
        ...

    def finalize(self, context: JobContext) -> None:
        ...


class BackupServiceError(Exception):
    """Raised by backup services to signal controlled job failures."""

    def __init__(self, message: str, errors: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.errors = errors or [message]


class JobEngine:
    """Coordinates lifecycle hooks for a backup job."""

    DEFAULT_STATUS = "success"

    def __init__(self, storage_adapter: StorageAdapter) -> None:
        self._storage = storage_adapter

    def run(self, job_config: JobConfig, service: BackupService, retention_days: int) -> JobResult:
        started_at = datetime.utcnow()
        workspace_path = Path(tempfile.mkdtemp(prefix=f"{job_config.name}-"))
        errors: List[str] = []
        status = self.DEFAULT_STATUS
        paths = self._storage.prepare_run(job_config, started_at)
        context = JobContext(
            job=job_config,
            started_at=started_at,
            storage_paths=paths,
            retention_days=retention_days,
            workspace=workspace_path,
        )

        try:
            service.prepare(context)
            service.execute(context)
            service.finalize(context)
        except BackupServiceError as exc:
            status = "failed"
            errors.extend(exc.errors)
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            errors.append(str(exc))
        finally:
            shutil.rmtree(workspace_path, ignore_errors=True)

        completed_at = datetime.utcnow()
        self._storage.enforce_retention(job_config, retention_days)
        return JobResult(
            job_name=job_config.name,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            errors=errors,
        )
