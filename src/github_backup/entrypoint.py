from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from .config import ConfigError, GitHubConfig, RepositoryConfig, load_config
from .github_api import GitHubAPI
from .logger import configure_logging, get_logger
from .manifest import Manifest, RepositoryManifest
from .metadata_backup import backup_organization_metadata, backup_repository_metadata
from .repo_backup import RepositoryBackupError, backup_repository
from .retention import enforce_retention

LOG = get_logger(__name__)


def main() -> int:
    config_path = Path(os.getenv("CONFIG_PATH", "/opt/github-backup/config/github-backup.yaml"))
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        configure_logging(os.getenv("LOG_LEVEL", "INFO"))
        LOG.error("Configuration error: %s", exc)
        return 2

    configure_logging(cfg.logging.level)
    LOG.info("Starting GitHub backup run using config %s", config_path)

    storage_base_env = os.getenv("STORAGE_BASE_PATH")
    storage_base = Path(storage_base_env) if storage_base_env else cfg.storage.base_path
    storage_base.mkdir(parents=True, exist_ok=True)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    execution_dir = storage_base / today
    execution_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir = execution_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    enforce_retention(storage_base, cfg.github.retention_days)

    started_at = datetime.utcnow()

    repositories: list[RepositoryManifest] = []
    errors: list[str] = []

    try:
        api = GitHubAPI(cfg.github.auth.token)
    except ConfigError as exc:
        LOG.error("Authentication error: %s", exc)
        return 2

    try:
        target_repositories = _resolve_target_repositories(api, cfg.github)
    except ConfigError as exc:
        LOG.error("Repository resolution error: %s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001
        LOG.error("Unexpected error while discovering repositories: %s", exc)
        LOG.debug("Traceback:\n%s", "".join(traceback.format_exc()))
        return 2

    if not target_repositories:
        LOG.warning("No repositories discovered for backup")
        return 0

    for repo_cfg in target_repositories:
        manifest_entry = RepositoryManifest(
            name=repo_cfg.name if "/" in repo_cfg.name else f"{cfg.github.organization}/{repo_cfg.name}",
            archive_path="",
        )
        try:
            backup_result = backup_repository(
                repo_cfg=repo_cfg,
                organization=cfg.github.organization,
                auth=cfg.github.auth,
                execution_dir=execution_dir,
                timestamp=started_at,
            )
            manifest_entry.archive_path = backup_result["archive_path"]
            manifest_entry.wiki_archive_path = backup_result.get("wiki_archive_path", "")

            metadata_counts = backup_repository_metadata(
                api=api,
                repo_cfg=repo_cfg,
                organization=cfg.github.organization,
                metadata_root=metadata_dir,
            )
            manifest_entry.metadata_counts = metadata_counts
        except RepositoryBackupError as exc:
            manifest_entry.backup_status = "failed"
            manifest_entry.error = str(exc)
            errors.append(f"Repository {manifest_entry.name} backup failed: {exc}")
            LOG.error("Repository backup failed for %s: %s", manifest_entry.name, exc)
        except Exception as exc:
            manifest_entry.backup_status = "failed"
            manifest_entry.error = str(exc)
            errors.append(f"Repository {manifest_entry.name} backup encountered error: {exc}")
            LOG.error("Unexpected error for %s: %s", manifest_entry.name, exc)
            LOG.debug("Traceback:\n%s", "".join(traceback.format_exc()))
        repositories.append(manifest_entry)

    org_counts = backup_organization_metadata(
        api=api,
        github_cfg=cfg.github,
        metadata_root=metadata_dir,
    )

    completed_at = datetime.utcnow()
    manifest = Manifest(
        started_at=started_at,
        completed_at=completed_at,
        retention_days=cfg.github.retention_days,
        repositories=repositories,
        organization_exports=org_counts,
        errors=errors,
    )
    manifest_path = execution_dir / "manifest.json"
    manifest.write(manifest_path)
    LOG.info("Backup manifest written to %s", manifest_path)

    if errors:
        LOG.warning("Backup completed with errors")
        return 1

    LOG.info("Backup completed successfully")
    return 0


def _resolve_target_repositories(api: GitHubAPI, github_cfg: GitHubConfig) -> list[RepositoryConfig]:
    repositories = list(github_cfg.repositories)

    if github_cfg.include_all_repositories:
        repositories = _discover_all_repositories(api, github_cfg, repositories)

    return repositories


def _discover_all_repositories(
    api: GitHubAPI,
    github_cfg: GitHubConfig,
    existing_repositories: list[RepositoryConfig],
) -> list[RepositoryConfig]:
    if not github_cfg.organization:
        raise ConfigError("GitHub organization must be set to discover repositories automatically")

    discovered: list[RepositoryConfig] = []
    seen = {repo.name for repo in existing_repositories}

    for repo in api.iterate(f"orgs/{github_cfg.organization}/repos", {"type": "all"}):
        full_name = repo.get("full_name")
        if not full_name or full_name in seen:
            continue
        discovered.append(RepositoryConfig(name=full_name))
        seen.add(full_name)

    return existing_repositories + discovered


if __name__ == "__main__":
    sys.exit(main())
