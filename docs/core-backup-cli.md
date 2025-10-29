# Core Backup CLI Usage

The `core_backup` package exposes a lightweight orchestrator for running declarative backup jobs. In this repository the only bundled service is the GitHub connector, but the CLI remains generic so the same interface can drive future services.

## Invocation
```bash
python -m core_backup.cli --config /path/to/core-backup.yaml
```

### Arguments
- `--config`: Path to the YAML configuration (defaults to `CORE_BACKUP_CONFIG` or `/opt/core-backup/config/core-backup.yaml`).
- `--job`: Restrict execution to one or more named jobs. Omit to run every job in the file.
- `--list-jobs`: Print job names and exit.
- `--log-level`: Overrides `LOG_LEVEL` (default `INFO`).

## Sample Configuration
See `config/core-backup.yaml.example` for the full schema. The GitHub connector supports automatic discovery when repositories are omitted:
```yaml
jobs:
  - name: github-org-backup
    service: github
    target_storage: local
    options:
      organization: my-org
      auth:
        token_env: GITHUB_TOKEN
      repositories: []               # empty list => back up every repo in the org
      organization_exports:
        members: true
        projects: true
storage:
  local:
    type: filesystem
    base_path: /mnt/backups/core
default_retention_days: 30
```

## Exit Codes
- `0`: All requested jobs completed successfully.
- `1`: One or more jobs failed (manifest still written with errors).
- `2`: Configuration error (invalid YAML/schema).

## Operational Notes
- Schedule the CLI via cron, systemd, or GitHub Actions using the Docker Compose wrapper documented in the project `README.md`.
- Configuration and secrets should live in the private `project-core-backup` repository and be mounted into the container via `BACKUP_CONFIG_DIR`.
- Future connectors can register with `core_backup.services.create_service`; update the CLI docs when new services ship.
