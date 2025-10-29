from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, root_validator, validator
from croniter import CroniterBadCronError, croniter


class ConfigurationError(Exception):
    """Raised when the core backup configuration is invalid."""


class SecretRef(BaseModel):
    """Reference to a secret stored in an environment variable or file."""

    env: Optional[str] = Field(default=None, description="Environment variable name.")
    file: Optional[Path] = Field(default=None, description="Path to a file containing the secret.")

    def resolve(self) -> Optional[str]:
        if self.env:
            value = os.getenv(self.env)
            if value:
                return value
        if self.file:
            file_path = Path(self.file)
            if file_path.exists():
                return file_path.read_text(encoding="utf-8").strip()
        return None


# --- Storage -----------------------------------------------------------------


class StorageConfig(BaseModel):
    type: Literal["filesystem"]
    base_path: Path

    @validator("base_path")
    def _expand_base_path(cls, value: Path) -> Path:  # noqa: N805
        return value.expanduser()


StorageConfigMap = Dict[str, StorageConfig]


# --- GitHub job options ------------------------------------------------------


class GitHubRepositoryOptions(BaseModel):
    name: str
    include_wiki: bool = False
    include_releases: bool = False
    include_projects: bool = False
    include_submodules: bool = False
    include_artifacts: bool = False


class GitHubOrganizationExports(BaseModel):
    members: bool = False
    teams: bool = False
    projects: bool = False


class GitHubAuthConfig(BaseModel):
    token: Optional[str] = Field(default=None, description="Explicit token string (discouraged).")
    token_env: Optional[str] = Field(default=None, description="Environment variable containing token.")
    ssh_key_path: Optional[Path] = None

    @root_validator
    def _require_secret(cls, values: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:  # noqa: N805
        token, token_env = values.get("token"), values.get("token_env")
        if not token and not token_env:
            raise ValueError("Either token or token_env must be provided for GitHub auth.")
        return values

    def resolved_token(self) -> Optional[str]:
        if self.token:
            return self.token
        if self.token_env:
            return os.getenv(self.token_env)
        return None


class GitHubJobOptions(BaseModel):
    organization: Optional[str] = Field(default=None, description="Organization scope for repositories.")
    repositories: List[GitHubRepositoryOptions]
    organization_exports: GitHubOrganizationExports = GitHubOrganizationExports()
    auth: GitHubAuthConfig
    include_actions_artifacts: bool = False
    retention_days: Optional[int] = None

    @validator("repositories")
    def _require_repositories(cls, value: List[GitHubRepositoryOptions]) -> List[GitHubRepositoryOptions]:  # noqa: N805
        if not value:
            raise ValueError("GitHub job must define at least one repository.")
        return value


# --- Job configuration -------------------------------------------------------


class JobConfig(BaseModel):
    name: str
    service: Literal["github"]
    target_storage: str = "default"
    schedule: Optional[str] = Field(default=None, description="Cron expression hint.")
    retention_days: Optional[int] = None
    options: GitHubJobOptions

    def effective_retention(self, fallback: int) -> int:
        if self.retention_days:
            return self.retention_days
        if isinstance(self.options, GitHubJobOptions) and self.options.retention_days:
            return self.options.retention_days
        return fallback


class NotificationsConfig(BaseModel):
    slack_webhook_env: Optional[str] = None

    def resolve_slack_webhook(self) -> Optional[str]:
        if not self.slack_webhook_env:
            return None
        return os.getenv(self.slack_webhook_env)


class CoreConfig(BaseModel):
    jobs: List[JobConfig]
    storage: StorageConfigMap
    notifications: NotificationsConfig = NotificationsConfig()
    default_retention_days: int = 30
    scheduler: Optional["SchedulerConfig"] = None

    @validator("jobs")
    def _require_jobs(cls, value: List[JobConfig]) -> List[JobConfig]:  # noqa: N805
        if not value:
            raise ValueError("At least one job must be configured.")
        return value

    @validator("storage")
    def _require_storage(cls, value: StorageConfigMap) -> StorageConfigMap:  # noqa: N805
        if not value:
            raise ValueError("At least one storage target must be configured.")
        return value

    @root_validator
    def _ensure_job_storage(cls, values: Dict[str, object]) -> Dict[str, object]:  # noqa: N805
        storage_map: StorageConfigMap = values.get("storage", {})
        jobs: List[JobConfig] = values.get("jobs", [])
        if storage_map and jobs:
            for job in jobs:
                if job.target_storage not in storage_map:
                    raise ValueError(f"Job '{job.name}' references unknown storage '{job.target_storage}'.")
        return values


def load_config(path: Path) -> CoreConfig:
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    try:
        return CoreConfig.parse_obj(raw)
    except Exception as exc:  # noqa: BLE001
        raise ConfigurationError(str(exc)) from exc


class SchedulerConfig(BaseModel):
    cron: str
    timezone: str = "UTC"
    run_on_startup: bool = True

    @validator("cron")
    def _validate_cron(cls, value: str) -> str:  # noqa: N805
        try:
            croniter(value, datetime.utcnow())
        except (CroniterBadCronError, ValueError) as exc:  # pragma: no cover - library errors
            raise ValueError(f"Invalid cron expression '{value}': {exc}") from exc
        return value

    @validator("timezone")
    def _validate_timezone(cls, value: str) -> str:  # noqa: N805
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:  # pragma: no cover - library errors
            raise ValueError(f"Unknown timezone '{value}'") from exc
        return value


CoreConfig.update_forward_refs(SchedulerConfig=SchedulerConfig)
