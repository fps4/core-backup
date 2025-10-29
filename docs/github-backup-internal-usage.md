# GitHub Backup Operations Guide

This document captures how we run the GitHub backup service while keeping configuration versioned and secrets external to Git.

## Repository Layout
- **Code and templates**: `core-backup/` (this repository) includes the Docker image, CLI, and example configuration under `config/`.
- **Authoritative config**: maintain your runtime YAML in `config/github-backup.yaml` (or another directory you reference through `BACKUP_CONFIG_DIR`); keep sensitive values out of Git.
- **Secrets**: store tokens, SSH keys, and webhooks in your secrets manager. Surface them at runtime via environment variables, Docker secrets, or mounted files.
- **Backups**: point `BACKUP_DATA_DIR` at the host directory where dated archives and manifests should land (e.g., `/srv/backups/github`).

## Running Backups
1. Clone this repository and update `config/github-backup.yaml` (copy from `config/github-backup.yaml.example` if you need a starting point).
2. Export the required environment variables before invoking Docker Compose:
   ```bash
   cd /path/to/core-backup
   BACKUP_CONFIG_DIR=$(pwd)/config \
   BACKUP_DATA_DIR=/srv/backups/github \
   GITHUB_TOKEN=... \
   docker compose -f docker/compose.yaml \
                  -f docker/compose.prod.yaml up -d --build
   ```
   - Override `BACKUP_CONFIG_DIR` if your configs live elsewhere.
   - Ensure `BACKUP_DATA_DIR` has sufficient storage and appropriate permissions.
   - Inject secrets through environment variables or Docker secrets; never commit them.
3. For recurring runs, integrate the same command into cron, systemd, or (later) GitHub Actions.
4. Optional: wrap the exports and compose invocation in a shell script checked into the repo so operators have a single entrypoint; reference secrets from your vault when the script executes.

## Configuration Tips
- Leave `github.repositories` empty to back up every repository in the organization automatically. The token must have read access to the organization and its private repositories.
- Override retention by setting `github.retention_days` or per-repo values.
- Use `notifications.slack_webhook_env` to alert on failures; resolve the webhook secret via your secret manager at runtime.

## Restore & Validation
- Backups are stored under `<BACKUP_DATA_DIR>/<YYYY-MM-DD>/`.
- Repository archives are bare mirrors (`*.tar.gz`). Restore with `tar -xzf repo.tar.gz && git clone repo.git`.
- Metadata lives under `metadata/` as JSON payloads exported by the GitHub API.
- The `manifest.json` file summarizes artifacts and errors for each run; inspect it when triaging alerts.

## Keeping Things in Sync
- Keep application code and configuration templates up to date by following the main branch of `core-backup`.
- For local development, run unit tests or dry runs from `core-backup`, and commit only redacted configuration examples—use environment variables for any sensitive values.
