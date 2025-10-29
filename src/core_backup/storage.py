from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import JobConfig, StorageConfig
from .job_engine import RunPaths
from .github.retention import enforce_retention


@dataclass
class FilesystemStorageAdapter:
    """Stores artifacts under a host-mounted filesystem."""

    name: str
    base_path: Path

    def prepare_run(self, job: JobConfig, started_at: datetime) -> RunPaths:
        job_root = self.base_path / job.name
        run_dir = job_root / started_at.strftime("%Y-%m-%d")
        metadata_dir = run_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return RunPaths(root=run_dir, metadata_dir=metadata_dir)

    def enforce_retention(self, job: JobConfig, retention_days: int) -> None:
        job_root = self.base_path / job.name
        enforce_retention(job_root, retention_days)


def build_storage_adapter(name: str, config: StorageConfig) -> FilesystemStorageAdapter:
    if config.type != "filesystem":
        raise ValueError(f"Unsupported storage type '{config.type}' for {name}")
    base_path = config.base_path
    base_path.mkdir(parents=True, exist_ok=True)
    return FilesystemStorageAdapter(name=name, base_path=base_path)
