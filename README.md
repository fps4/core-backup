# GitHub Backup

`github-backup` is a containerized utility that captures daily snapshots of GitHub repositories and related metadata. Each run mirrors the repositories, exports issues/PRs/projects, stores the artifacts under a date-based folder structure, and enforces time-based retention.

## Features
- Mirrors repositories (including optional wikis) and packages them as compressed archives.
- Exports repository issues, pull requests, releases, projects, and Actions artifacts (optional).
- Captures organization-level data such as members, teams, and projects.
- Applies retention pruning so only the most recent backups (default 30 days) are kept.
- Ships as a slim Python+Git Docker image ready for cron-driven execution.

## Quick Start
1. Copy `config/github-backup.yaml.example` (or create the file in a sibling private repository such as `../project-core-backup/config/github-backup.yaml`) and adjust values for your organization. Provide a GitHub token or SSH key via mounted secrets.
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

## Private Configuration Repository
To keep production configuration private while making this codebase public:
- Maintain a separate repo like `project-core-backup` that contains only secrets-free manifests (for example `config/github-backup.yaml`, SSH keys in a secrets store, and environment overrides).
- Clone the two repositories side-by-side: `core-backup/` (public code) and `project-core-backup/` (private config). The default Docker Compose file already binds `../../project-core-backup/config` into the container; override `BACKUP_CONFIG_DIR` if your layout differs.
- From inside `project-core-backup`, run:
  ```bash
  BACKUP_CONFIG_DIR=$(pwd)/config \
  BACKUP_DATA_DIR=/srv/backups/github \
  docker compose -f ../core-backup/docker/compose.yaml -f ../core-backup/docker/compose.prod.yaml up -d --build
  ```
  (Adjust the path to `core-backup` based on where you invoke the command.)
- Optional: add a wrapper script or GitHub Actions workflow inside `project-core-backup` that exports the same environment variables and delegates to the `core-backup` compose file, so operators only interact with the private repo.

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
