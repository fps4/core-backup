from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFAULT_RETENTION_DAYS = 30


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclasses.dataclass(frozen=True)
class AuthConfig:
    token_env: Optional[str] = None
    ssh_key_path: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        if not self.token_env:
            return None
        return os.getenv(self.token_env)


@dataclasses.dataclass(frozen=True)
class RepositoryConfig:
    name: str
    include_wiki: bool = False
    include_releases: bool = False
    include_projects: bool = False
    include_submodules: bool = False
    include_artifacts: bool = False


@dataclasses.dataclass(frozen=True)
class OrganizationExportsConfig:
    members: bool = False
    teams: bool = False
    projects: bool = False


@dataclasses.dataclass(frozen=True)
class GitHubConfig:
    organization: Optional[str]
    auth: AuthConfig
    retention_days: int
    repositories: List[RepositoryConfig]
    organization_exports: OrganizationExportsConfig
    include_actions_artifacts: bool = False


@dataclasses.dataclass(frozen=True)
class StorageConfig:
    base_path: Path


@dataclasses.dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    emit_metrics: bool = False


@dataclasses.dataclass(frozen=True)
class NotificationsConfig:
    slack_webhook_env: Optional[str] = None

    @property
    def slack_webhook(self) -> Optional[str]:
        if not self.slack_webhook_env:
            return None
        return os.getenv(self.slack_webhook_env)


@dataclasses.dataclass(frozen=True)
class RootConfig:
    github: GitHubConfig
    storage: StorageConfig
    logging: LoggingConfig
    notifications: NotificationsConfig


def _parse_auth(data: Dict[str, Any]) -> AuthConfig:
    return AuthConfig(
        token_env=data.get("token_env"),
        ssh_key_path=data.get("ssh_key_path"),
    )


def _parse_repository(repo_data: Dict[str, Any]) -> RepositoryConfig:
    if "name" not in repo_data:
        raise ConfigError("Repository entry missing 'name'")

    return RepositoryConfig(
        name=repo_data["name"],
        include_wiki=bool(repo_data.get("include_wiki", False)),
        include_releases=bool(repo_data.get("include_releases", False)),
        include_projects=bool(repo_data.get("include_projects", False)),
        include_submodules=bool(repo_data.get("include_submodules", False)),
        include_artifacts=bool(repo_data.get("include_artifacts", False)),
    )


def _parse_org_exports(data: Dict[str, Any]) -> OrganizationExportsConfig:
    return OrganizationExportsConfig(
        members=bool(data.get("members", False)),
        teams=bool(data.get("teams", False)),
        projects=bool(data.get("projects", False)),
    )


def _parse_github(data: Dict[str, Any]) -> GitHubConfig:
    if "repositories" not in data or not data["repositories"]:
        raise ConfigError("GitHub config must include at least one repository")

    retention = data.get("retention_days", DEFAULT_RETENTION_DAYS)
    if retention <= 0:
        raise ConfigError("Retention must be positive")

    return GitHubConfig(
        organization=data.get("organization"),
        auth=_parse_auth(data.get("auth", {})),
        retention_days=retention,
        repositories=[_parse_repository(repo) for repo in data["repositories"]],
        organization_exports=_parse_org_exports(data.get("organization_exports", {})),
        include_actions_artifacts=bool(data.get("include_actions_artifacts", False)),
    )


def _parse_storage(data: Dict[str, Any]) -> StorageConfig:
    base_path = data.get("base_path")
    if not base_path:
        raise ConfigError("Storage base_path must be set")
    return StorageConfig(base_path=Path(base_path))


def _parse_logging(data: Dict[str, Any]) -> LoggingConfig:
    return LoggingConfig(
        level=data.get("level", "INFO").upper(),
        emit_metrics=bool(data.get("emit_metrics", False)),
    )


def _parse_notifications(data: Dict[str, Any]) -> NotificationsConfig:
    return NotificationsConfig(
        slack_webhook_env=data.get("slack_webhook_env"),
    )


def load_config(path: Path) -> RootConfig:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if "github" not in raw:
        raise ConfigError("Top-level 'github' block missing")

    return RootConfig(
        github=_parse_github(raw["github"]),
        storage=_parse_storage(raw.get("storage", {})),
        logging=_parse_logging(raw.get("logging", {})),
        notifications=_parse_notifications(raw.get("notifications", {})),
    )
