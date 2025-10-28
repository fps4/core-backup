from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core_backup.config import GitHubAuthConfig, JobConfig
from core_backup.job_engine import BackupService, BackupServiceError, JobContext
from github_backup.config import (
    AuthConfig as LegacyAuthConfig,
    GitHubConfig as LegacyGitHubConfig,
    OrganizationExportsConfig as LegacyOrganizationExportsConfig,
    RepositoryConfig as LegacyRepositoryConfig,
)
from github_backup.github_api import GitHubAPI
from github_backup.manifest import Manifest, RepositoryManifest
from github_backup.metadata_backup import (
    backup_organization_metadata,
    backup_repository_metadata,
)
from github_backup.repo_backup import RepositoryBackupError, backup_repository


class GitHubBackupService(BackupService):
    """Adapter that runs the legacy GitHub backup workflow inside the new job engine."""

    def __init__(self, job: JobConfig) -> None:
        if job.service != "github":
            raise ValueError(f"GitHubBackupService cannot handle service '{job.service}'")
        self._job = job
        self._options = job.options
        self._api: Optional[GitHubAPI] = None
        self._legacy_config: Optional[LegacyGitHubConfig] = None
        self._inline_token_env: Optional[str] = None

    # Job lifecycle ---------------------------------------------------------
    def prepare(self, context: JobContext) -> None:
        self._inline_token_env = None
        token = self._options.auth.resolved_token()
        if not token:
            raise BackupServiceError(
                "GitHub token could not be resolved from configuration or environment."
            )

        legacy_auth = self._build_legacy_auth(self._options.auth, token)
        repositories = [
            LegacyRepositoryConfig(
                name=repo.name,
                include_wiki=repo.include_wiki,
                include_releases=repo.include_releases,
                include_projects=repo.include_projects,
                include_submodules=repo.include_submodules,
                include_artifacts=repo.include_artifacts,
            )
            for repo in self._options.repositories
        ]
        legacy_exports = LegacyOrganizationExportsConfig(
            members=self._options.organization_exports.members,
            teams=self._options.organization_exports.teams,
            projects=self._options.organization_exports.projects,
        )

        self._legacy_config = LegacyGitHubConfig(
            organization=self._options.organization,
            auth=legacy_auth,
            retention_days=context.retention_days,
            repositories=repositories,
            organization_exports=legacy_exports,
            include_actions_artifacts=self._options.include_actions_artifacts,
        )
        self._api = GitHubAPI(token)

    def execute(self, context: JobContext) -> None:
        if not self._api or not self._legacy_config:
            raise BackupServiceError("GitHub service not prepared.")

        execution_dir = context.storage_paths.root
        metadata_dir = context.storage_paths.metadata_dir
        execution_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        repositories: List[RepositoryManifest] = []
        errors: List[str] = []

        for repo_cfg in self._legacy_config.repositories:
            repo_slug = self._resolve_repo_slug(repo_cfg.name)
            manifest_entry = RepositoryManifest(
                name=repo_slug,
                archive_path="",
            )
            try:
                backup_result = backup_repository(
                    repo_cfg=repo_cfg,
                    organization=self._legacy_config.organization,
                    auth=self._legacy_config.auth,
                    execution_dir=execution_dir,
                    timestamp=context.started_at,
                )
                manifest_entry.archive_path = backup_result["archive_path"]
                manifest_entry.wiki_archive_path = backup_result.get("wiki_archive_path", "")

                metadata_counts = backup_repository_metadata(
                    api=self._api,
                    repo_cfg=repo_cfg,
                    organization=self._legacy_config.organization,
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
            github_cfg=self._legacy_config,
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
        if self._inline_token_env and self._inline_token_env in os.environ:
            os.environ.pop(self._inline_token_env, None)

    # Internal helpers ------------------------------------------------------
    def _build_legacy_auth(self, auth_config: GitHubAuthConfig, token: str) -> LegacyAuthConfig:
        token_env = auth_config.token_env
        if auth_config.token and not auth_config.token_env:
            token_env = f"CORE_BACKUP_GITHUB_TOKEN_{uuid4().hex.upper()}"
            os.environ[token_env] = token
            self._inline_token_env = token_env
        ssh_key_path = str(auth_config.ssh_key_path) if auth_config.ssh_key_path else None
        return LegacyAuthConfig(token_env=token_env, ssh_key_path=ssh_key_path)

    def _resolve_repo_slug(self, name: str) -> str:
        if "/" in name:
            return name
        if not self._options.organization:
            raise BackupServiceError(f"Repository '{name}' missing organization context.")
        return f"{self._options.organization}/{name}"
