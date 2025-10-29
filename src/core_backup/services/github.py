from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core_backup.config import GitHubRepositoryOptions, JobConfig
from core_backup.github import (
    GitHubAPI,
    Manifest,
    RepositoryBackupError,
    RepositoryManifest,
    backup_organization_metadata,
    backup_repository,
    backup_repository_metadata,
)
from core_backup.job_engine import BackupService, BackupServiceError, JobContext


class GitHubBackupService(BackupService):
    """Backup service that mirrors repositories and metadata from GitHub."""

    def __init__(self, job: JobConfig) -> None:
        if job.service != "github":
            raise ValueError(f"GitHubBackupService cannot handle service '{job.service}'")
        self._job = job
        self._options = job.options
        self._api: Optional[GitHubAPI] = None
        self._token: Optional[str] = None

    # Job lifecycle ---------------------------------------------------------
    def prepare(self, context: JobContext) -> None:
        token = self._options.auth.resolved_token()
        if not token:
            raise BackupServiceError(
                "GitHub token could not be resolved from configuration or environment."
            )

        try:
            self._api = GitHubAPI(token)
        except ValueError as exc:
            raise BackupServiceError(str(exc)) from exc

        self._token = token

    def execute(self, context: JobContext) -> None:
        if not self._api:
            raise BackupServiceError("GitHub service not prepared.")

        execution_dir = context.storage_paths.root
        metadata_dir = context.storage_paths.metadata_dir
        execution_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        repositories: List[RepositoryManifest] = []
        errors: List[str] = []

        repo_configs = self._get_repository_configs()

        for repo_cfg in repo_configs:
            repo_slug = self._resolve_repo_slug(repo_cfg.name)
            manifest_entry = RepositoryManifest(
                name=repo_slug,
                archive_path="",
            )
            try:
                backup_result = backup_repository(
                    repo_cfg=repo_cfg,
                    organization=self._options.organization,
                    auth=self._options.auth,
                    token=self._token,
                    execution_dir=execution_dir,
                    timestamp=context.started_at,
                )
                manifest_entry.archive_path = backup_result["archive_path"]
                manifest_entry.wiki_archive_path = backup_result.get("wiki_archive_path", "")

                metadata_counts = backup_repository_metadata(
                    api=self._api,
                    repo_cfg=repo_cfg,
                    organization=self._options.organization,
                    metadata_root=metadata_dir,
                )
                manifest_entry.metadata_counts = metadata_counts
            except RepositoryBackupError as exc:
                manifest_entry.backup_status = "failed"
                manifest_entry.error = str(exc)
                errors.append(f"Repository {manifest_entry.name} backup failed: {exc}")
            except Exception as exc:  # noqa: BLE001
                manifest_entry.backup_status = "failed"
                manifest_entry.error = str(exc)
                errors.append(f"Repository {manifest_entry.name} backup error: {exc}")
            repositories.append(manifest_entry)

        org_counts = backup_organization_metadata(
            api=self._api,
            organization=self._options.organization,
            exports=self._options.organization_exports,
            metadata_root=metadata_dir,
        )

        manifest = Manifest(
            started_at=context.started_at,
            completed_at=datetime.utcnow(),
            retention_days=context.retention_days,
            repositories=repositories,
            organization_exports=org_counts,
            errors=errors,
        )
        manifest.write(execution_dir / "manifest.json")

        if errors:
            raise BackupServiceError("GitHub backup completed with errors.", errors=errors)

    def finalize(self, context: JobContext) -> None:  # noqa: ARG002
        # Nothing to clean up currently; placeholder for future hooks.
        return

    # Internal helpers ------------------------------------------------------
    def _get_repository_configs(self) -> List[GitHubRepositoryOptions]:
        repo_configs = self._options.repositories or []
        if repo_configs:
            return repo_configs

        if not self._api:
            raise BackupServiceError("GitHub service not prepared.")

        organization = self._options.organization
        if not organization:
            raise BackupServiceError(
                "Cannot determine repositories to back up: no repositories listed and no organization provided."
            )

        try:
            discovered = [
                GitHubRepositoryOptions(name=item["full_name"])
                for item in self._api.iterate(
                    f"/orgs/{organization}/repos",
                    params={"type": "all"},
                )
                if item.get("full_name")
            ]
        except Exception as exc:  # noqa: BLE001
            raise BackupServiceError(
                f"Failed to list repositories for organization '{organization}': {exc}"
            ) from exc

        if not discovered:
            raise BackupServiceError(
                f"No repositories found for organization '{organization}'."
            )

        return discovered

    def _resolve_repo_slug(self, name: str) -> str:
        if "/" in name:
            return name
        if not self._options.organization:
            raise BackupServiceError(f"Repository '{name}' missing organization context.")
        return f"{self._options.organization}/{name}"
