from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from requests import HTTPError

from .config import GitHubConfig, OrganizationExportsConfig, RepositoryConfig
from .github_api import GitHubAPI

LOG = logging.getLogger(__name__)


def backup_repository_metadata(
    api: GitHubAPI,
    repo_cfg: RepositoryConfig,
    organization: Optional[str],
    metadata_root: Path,
) -> Dict[str, int]:
    repo_slug = repo_cfg.name if "/" in repo_cfg.name else f"{organization}/{repo_cfg.name}"
    repo_dir = metadata_root / repo_slug.replace("/", "_")
    repo_dir.mkdir(parents=True, exist_ok=True)

    counts: Dict[str, int] = {}

    issues = list(api.iterate(f"repos/{repo_slug}/issues", {"state": "all"}))
    _write_json(repo_dir / "issues.json", issues)
    counts["issues"] = len(issues)

    pulls = list(api.iterate(f"repos/{repo_slug}/pulls", {"state": "all"}))
    _write_json(repo_dir / "pull_requests.json", pulls)
    counts["pull_requests"] = len(pulls)

    if repo_cfg.include_releases:
        releases = list(api.iterate(f"repos/{repo_slug}/releases"))
        _write_json(repo_dir / "releases.json", releases)
        counts["releases"] = len(releases)

    if repo_cfg.include_projects:
        projects = _fetch_classic_projects(
            api,
            f"repos/{repo_slug}/projects",
            identifier=repo_slug,
            scope="repository",
        )
        _write_json(repo_dir / "projects.json", projects)
        counts["projects"] = len(projects)

    if repo_cfg.include_artifacts:
        artifacts = list(api.iterate(f"repos/{repo_slug}/actions/artifacts"))
        _write_json(repo_dir / "actions_artifacts.json", artifacts)
        counts["actions_artifacts"] = len(artifacts)

    return counts


def backup_organization_metadata(
    api: GitHubAPI,
    github_cfg: GitHubConfig,
    metadata_root: Path,
) -> Dict[str, int]:
    org = github_cfg.organization
    if not org:
        return {}

    counts: Dict[str, int] = {}
    org_dir = metadata_root / org
    org_dir.mkdir(parents=True, exist_ok=True)
    exports = github_cfg.organization_exports

    if exports.members:
        members = list(api.iterate(f"orgs/{org}/members"))
        _write_json(org_dir / "members.json", members)
        counts["org_members"] = len(members)

    if exports.teams:
        teams = list(api.iterate(f"orgs/{org}/teams"))
        _write_json(org_dir / "teams.json", teams)
        counts["org_teams"] = len(teams)

    if exports.projects:
        projects = _fetch_classic_projects(
            api,
            f"orgs/{org}/projects",
            identifier=org,
            scope="organization",
        )
        _write_json(org_dir / "projects.json", projects)
        counts["org_projects"] = len(projects)

    return counts


def _write_json(path: Path, payload: List[Dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _fetch_classic_projects(
    api: GitHubAPI,
    path: str,
    *,
    identifier: str,
    scope: str,
) -> List[Dict]:
    try:
        return list(api.iterate(path))
    except HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status == 410:
            LOG.info(
                "Skipping classic Projects export for %s '%s': API returned 410 (deprecated)",
                scope,
                identifier,
            )
            return []
        raise
