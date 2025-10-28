from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .config import CoreConfig, JobConfig, ConfigurationError, load_config
from .job_engine import BackupService, JobEngine, JobResult
from .storage import FilesystemStorageAdapter, build_storage_adapter

ServiceFactory = Callable[[JobConfig], BackupService]


class BackupOrchestrator:
    """High-level orchestrator that runs backup jobs through the job engine."""

    def __init__(self, config: CoreConfig, service_factory: ServiceFactory) -> None:
        self._config = config
        self._service_factory = service_factory
        self._storage_adapters: Dict[str, FilesystemStorageAdapter] = {
            name: build_storage_adapter(name, storage_cfg)
            for name, storage_cfg in config.storage.items()
        }

    def run(self, job_names: Optional[Sequence[str]] = None) -> List[JobResult]:
        jobs = self._select_jobs(job_names)
        results: List[JobResult] = []
        for job in jobs:
            adapter = self._storage_adapters[job.target_storage]
            retention_days = job.effective_retention(self._config.default_retention_days)
            try:
                service = self._service_factory(job)
            except Exception as exc:  # noqa: BLE001
                now = datetime.utcnow()
                results.append(
                    JobResult(
                        job_name=job.name,
                        status="failed",
                        started_at=now,
                        completed_at=now,
                        errors=[f"Service instantiation failed: {exc}"],
                    )
                )
                continue

            engine = JobEngine(storage_adapter=adapter)
            result = engine.run(job, service, retention_days=retention_days)
            results.append(result)
        return results

    def _select_jobs(self, job_names: Optional[Sequence[str]]) -> Iterable[JobConfig]:
        if job_names:
            name_set = set(job_names)
            missing = name_set - {job.name for job in self._config.jobs}
            if missing:
                missing_str = ", ".join(sorted(missing))
                raise ConfigurationError(f"Unknown job(s) requested: {missing_str}")
            for job in self._config.jobs:
                if job.name in name_set:
                    yield job
        else:
            yield from self._config.jobs


def load_orchestrator(config_path: str, service_factory: ServiceFactory) -> BackupOrchestrator:
    config = load_config(Path(config_path))
    return BackupOrchestrator(config=config, service_factory=service_factory)
