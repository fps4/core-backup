# GitHub Backup

`github-backup` is a containerized utility that captures daily snapshots of GitHub repositories and related metadata. Each run mirrors the repositories, exports issues/PRs/projects, stores the artifacts under a date-based folder structure, and enforces time-based retention.

## Features
- Mirrors repositories (including optional wikis) and packages them as compressed archives.
- Exports repository issues, pull requests, releases, projects, and Actions artifacts (optional).
- Captures organization-level data such as members, teams, and projects.
- Applies retention pruning so only the most recent backups (default 30 days) are kept.
- Ships as a slim Python+Git Docker image ready for cron-driven execution.

## Quick Start
1. Copy `config/github-backup.yaml.example` to `config/github-backup.yaml` (or point `CONFIG_PATH` at your own file) and adjust values for your organization. Provide a GitHub token or SSH key via mounted secrets.
2. Build the image:
   ```bash
   docker build -t github-backup .
   ```
3. Run the container on a schedule, mounting your config and backup volume:
   ```bash
   docker run --rm \
     -v /path/to/config:/opt/github-backup/config:ro \
     -v /mnt/backups/github:/mnt/backups/github \
     -e GITHUB_TOKEN=... \
     github-backup
   ```

## Configuration
The service is configured via YAML (see `config/github-backup.yaml.example`). Key sections:
- `github.repositories`: Optional list of repositories to back up, with per-repo flags. When omitted or empty and an organization is provided, the backup automatically targets every repository in the organization.
- `github.organization_exports`: Enable organization-level exports.
- `storage.base_path`: Host mount where dated backup folders are created.
- `logging` / `notifications`: Optional log level and webhook parameters.

Secrets (e.g., `GITHUB_TOKEN`) should be provided through environment variables or mounted files rather than embedded in the YAML.

## Configuration Layout
Production configuration now lives alongside the code in this repository under `config/`. Keep secrets (tokens, SSH keys, webhooks) in your preferred secrets manager and inject them at runtime via environment variables, Docker secrets, or mounted files. When running via Docker Compose:
- Point `BACKUP_CONFIG_DIR` at the directory that contains your finalized YAML (defaults to `${PWD}/config` when invoked from the repo root).
- Set `BACKUP_DATA_DIR` to the host filesystem path where you want dated backups stored.
- Export `GITHUB_TOKEN` (and any other credentials) before invoking `docker compose -f docker/compose.yaml -f docker/compose.prod.yaml up -d --build`.
- Wrap these exports in a script or GitHub Actions workflow if you want a single command for operators; commit only the script templates—reference secrets from your vault at runtime.

## Local Development
Install dependencies (Python 3.11+):
```bash
pip install -r requirements.txt
```
Run locally with environment variables pointing at your configuration:
```bash
export CONFIG_PATH=./config/github-backup.yaml
export STORAGE_BASE_PATH=./backups
export GITHUB_TOKEN=...
python -m github_backup.entrypoint
```

## Roadmap Ideas
- Additional collectors (e.g., GitHub Actions workflow runs, audit logs).
- Pluggable exporters for other services using the same retention engine.
- Optional encryption/compression strategies for archives.

## License
Released under the [MIT License](LICENSE).
