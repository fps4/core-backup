# Core Backup CLI Usage

The `core_backup` package now exposes a generic job orchestrator capable of running multiple backup connectors. Use the CLI module to execute jobs defined in a YAML configuration file.

## Invocation
```bash
python -m core_backup.cli --config /path/to/core-backup.yaml
```

### Arguments
- `--config`: Path to the YAML configuration (defaults to `CORE_BACKUP_CONFIG` env var or `/opt/core-backup/config/core-backup.yaml`).
- `--job`: Restrict execution to the named job. Repeat flag to run multiple jobs.
- `--list-jobs`: Print job names and exit without running backups.
- `--log-level`: Override log verbosity (defaults to `LOG_LEVEL` env var or `INFO`).

## Sample Configuration
See `config/core-backup.yaml.example` for a full example. Configuration schema overview:
```yaml
jobs:
  - name: github-daily
    service: github
    target_storage: local
    retention_days: 30               # Optional; falls back to default_retention_days.
    options:
      organization: my-org
      auth:
        token_env: GITHUB_TOKEN
      repositories:
        - name: repo-one
          include_projects: true
        - name: repo-two
          include_releases: true
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

## Next Steps
- Create additional service connectors (MongoDB, Docker volume).
- Extend storage adapters (S3, NFS).
- Add integration tests (e.g., docker-compose-based) to exercise multi-job runs end-to-end.
