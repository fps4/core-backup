# GitHub Backup Operations Guide

This document captures how we run the GitHub backup service while keeping sensitive configuration private.

## Repository Layout
- **Public code**: `core-backup` (this repository) contains the Docker image, CLI, and service implementation.
- **Private configuration**: `project-core-backup` (private repo) stores YAML configs, environment overrides, and references to secrets (never the raw secrets themselves).
- Repos should live as siblings, e.g.:
  ```
  ~/Projects/
    core-backup/
    project-core-backup/
  ```

## Running Backups from `project-core-backup`
1. Clone both repositories side-by-side.
2. In `project-core-backup`, maintain `config/github-backup.yaml` and any additional files the container should mount.
3. Schedule or manually run the stack:
   ```bash
   cd ../project-core-backup
   BACKUP_CONFIG_DIR=$(pwd)/config \
   BACKUP_DATA_DIR=/srv/backups/github \
   GITHUB_TOKEN=... \
   docker compose -f ../core-backup/docker/compose.yaml \
                  -f ../core-backup/docker/compose.prod.yaml up -d --build
   ```
   - `BACKUP_CONFIG_DIR` should point at the private config directory.
   - `BACKUP_DATA_DIR` is the host path where dated backups will be written.
   - Provide credentials via environment variables or Docker secrets; never commit them.

4. Optionally wrap the compose call in a script or GitHub Actions workflow inside `project-core-backup` so operators only interact with that private repo.

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
- Treat `core-backup` as the upstream; avoid editing code inside `project-core-backup`.
- For local development, run unit tests or dry runs from `core-backup` but keep sample configs under `project-core-backup` to avoid leaking internal details.
