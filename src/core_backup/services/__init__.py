from __future__ import annotations

from core_backup.config import JobConfig
from core_backup.job_engine import BackupService

from .github import GitHubBackupService


def create_service(job: JobConfig) -> BackupService:
    if job.service == "github":
        return GitHubBackupService(job)
    raise ValueError(f"No service connector registered for '{job.service}'.")
