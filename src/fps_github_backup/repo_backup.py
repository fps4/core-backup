from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .config import AuthConfig, RepositoryConfig

LOG = logging.getLogger(__name__)


class RepositoryBackupError(Exception):
    """Raised when repository backup fails."""


def backup_repository(
    repo_cfg: RepositoryConfig,
    organization: Optional[str],
    auth: AuthConfig,
    execution_dir: Path,
    timestamp: datetime,
) -> Dict[str, str]:
    repo_slug = _resolve_repo_slug(repo_cfg.name, organization)
    clone_url = _build_clone_url(repo_slug, auth)
    work_root = Path(tempfile.mkdtemp(prefix="github-backup-"))
    archive_name = f"{repo_slug.replace('/', '_')}_{timestamp.strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    archive_path = execution_dir / archive_name

    try:
        mirror_path = work_root / "mirror"
        mirror_path.mkdir(parents=True, exist_ok=True)
        repo_path = mirror_path / f"{repo_slug.replace('/', '_')}.git"

        if repo_path.exists():
            shutil.rmtree(repo_path)

        _clone_mirror(clone_url, repo_path, auth)
        _package_repository(repo_path, archive_path)

        wiki_archive = None
        if repo_cfg.include_wiki:
            wiki_url = clone_url.replace(".git", ".wiki.git")
            wiki_path = mirror_path / f"{repo_slug.replace('/', '_')}.wiki.git"
            _clone_mirror(wiki_url, wiki_path, auth, allow_fail=True)
            if wiki_path.exists():
                wiki_archive = archive_path.with_name(archive_path.stem + ".wiki.tar.gz")
                _package_repository(wiki_path, wiki_archive)

        return {
            "repository": repo_slug,
            "archive_path": str(archive_path),
            "wiki_archive_path": str(wiki_archive) if wiki_archive else "",
        }
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def _resolve_repo_slug(name: str, organization: Optional[str]) -> str:
    if "/" in name:
        return name
    if not organization:
        raise RepositoryBackupError(f"Repository '{name}' missing organization context")
    return f"{organization}/{name}"


def _build_clone_url(repo_slug: str, auth: AuthConfig) -> str:
    if auth.token:
        return f"https://x-access-token:{auth.token}@github.com/{repo_slug}.git"
    if auth.ssh_key_path:
        return f"git@github.com:{repo_slug}.git"
    raise RepositoryBackupError("No authentication credentials configured for git clone")


def _clone_mirror(clone_url: str, destination: Path, auth: AuthConfig, allow_fail: bool = False) -> None:
    env = os.environ.copy()
    if auth.ssh_key_path and not auth.token:
        env["GIT_SSH_COMMAND"] = f"ssh -i {auth.ssh_key_path} -o StrictHostKeyChecking=no"

    cmd = ["git", "clone", "--mirror", clone_url, str(destination)]
    LOG.info("Cloning repository to %s", destination)
    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        if allow_fail:
            LOG.warning("Optional repository clone failed: %s", exc.stderr.decode("utf-8", "ignore"))
            return
        LOG.error("git clone failed: %s", exc.stderr.decode("utf-8", "ignore"))
        raise RepositoryBackupError("Failed to clone repository") from exc


def _package_repository(repo_path: Path, archive_path: Path) -> None:
    LOG.info("Creating archive %s", archive_path)
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(repo_path, arcname=repo_path.name)
