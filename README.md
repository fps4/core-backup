# GitHub Backup

`github-backup` is a containerized utility that captures daily snapshots of GitHub repositories and related metadata. Each run mirrors the repositories, exports issues/PRs/projects, stores the artifacts under a date-based folder structure, and enforces time-based retention.

## Features
- Mirrors repositories (including optional wikis) and packages them as compressed archives.
- Exports repository issues, pull requests, releases, projects, and Actions artifacts (optional).
- Captures organization-level data such as members, teams, and projects.
- Applies retention pruning so only the most recent backups (default 30 days) are kept.
- Ships as a slim Python+Git Docker image ready for cron-driven execution.

## Quick Start
1. Copy `config/core-backup.yaml.example` to `config/core-backup.yaml` (or point `CORE_BACKUP_CONFIG` at your own file) and adjust values for your organization. Provide a GitHub token or SSH key via mounted secrets.
2. Build the image:
   ```bash
   docker build -t github-backup .
   ```
3. Run the container, mounting your config and backup volume:
   ```bash
   docker run --rm \
     -v /path/to/config:/opt/core-backup/config:ro \
     -v /mnt/backup/github:/mnt/backup/core \
     -e GITHUB_TOKEN=... \
     github-backup
   ```

## Configuration
The orchestrator is configured via YAML (see `config/core-backup.yaml.example`). Key sections:
- `jobs`: Named backup jobs that reference a service (`github` today) and storage target. Each job provides authentication, repository options, and retention overrides.
- `storage`: Host mounts where dated backup folders are created. The filesystem adapter writes `<job>/<YYYY-MM-DD>/`.
- `notifications`: Optional Slack webhook reference.
- `default_retention_days`: Fallback for jobs that don’t set retention explicitly.
- `scheduler`: Optional cron expression to keep the container running and trigger all jobs automatically (see below).

Secrets (e.g., `GITHUB_TOKEN`) should be provided through environment variables or mounted files rather than embedded in the YAML.

## Configuration Layout
Production configuration now lives alongside the code in this repository under `config/`. Keep secrets (tokens, SSH keys, webhooks) in your preferred secrets manager and inject them at runtime via environment variables, Docker secrets, or mounted files. When running via Docker Compose:
- Point `BACKUP_CONFIG_DIR` at the directory that contains your finalized YAML (defaults to `${PWD}/config` when invoked from the repo root).
- Set `BACKUP_DATA_DIR` to the host filesystem path where you want dated backups stored.
- Export `GITHUB_TOKEN` (and any other credentials) before invoking `docker compose -f docker/compose.yaml -f docker/compose.prod.yaml up -d --build`.
- Wrap these exports in a script or GitHub Actions workflow if you want a single command for operators; commit only the script templates—reference secrets from your vault at runtime.

### Built-in Scheduler

Add a `scheduler` block to `config/core-backup.yaml` to keep the container idling between runs:

```yaml
scheduler:
  cron: "0 3 * * *"   # run daily at 03:00
  timezone: "America/New_York"
  run_on_startup: true # optional immediate run when the container starts
```

When the scheduler is present, the process remains up, executes the configured jobs on the cron cadence, and honours graceful shutdown (`docker stop`). Omit the block (or run `docker compose run --rm core-backup`) for one-shot backups.

## Local Development
Install dependencies (Python 3.11+):
```bash
pip install -r requirements.txt
```
Run locally with environment variables pointing at your configuration:
```bash
export CORE_BACKUP_CONFIG=./config/core-backup.yaml
export GITHUB_TOKEN=...
python -m core_backup.cli
```

## Roadmap Ideas
- Additional collectors (e.g., GitHub Actions workflow runs, audit logs).
- Pluggable exporters for other services using the same retention engine.
- Optional encryption/compression strategies for archives.

## License
Released under the [MIT License](LICENSE).
