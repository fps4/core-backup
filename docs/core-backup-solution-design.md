# Core Backup Solution Overview

## Purpose
`core-backup` delivers a container-friendly runtime for declarative backup jobs. The current release focuses on GitHub organizations, but the shared plumbing (CLI, orchestrator, storage abstractions) keeps the door open for additional services without reworking deployments.

## Architecture
```
┌─────────────────┐      ┌──────────────────────┐      ┌────────────────────┐
│ core_backup CLI │ ---> │ Backup Orchestrator │ ---> │ Service Connector │
└─────────────────┘      └─────────┬────────────┘      └─────────┬──────────┘
                                    │                           │
                                    ▼                           ▼
                              Job execution             GitHub repositories,
                              tracking & retention       metadata exports, manifests
```

- **CLI / Entrypoint**: Loads configuration, selects jobs to run, and configures logging.
- **Orchestrator**: Applies retention policies, executes jobs, aggregates results, and emits status.
- **Service Connector**: `github_backup` mirrors repositories, exports metadata, and produces manifests. Additional connectors can register with `core_backup.services.create_service`.
- **Storage**: Host volume mounted at `/mnt/backups/github`. Each run writes `<YYYY-MM-DD>/<repo>_<timestamp>.tar.gz`, metadata directories, and `manifest.json`.

## Configuration Model
- Jobs are defined in `core-backup.yaml`, referencing named storage targets and service-specific `options`.
- GitHub options support two modes:
  - Explicit `repositories` list, with per-repository toggles.
  - Empty or omitted `repositories` plus `organization`, which triggers automatic discovery of every repository in the org at runtime.
- Secrets are referenced indirectly (`token_env`, SSH key paths) and injected via environment variables or mounted files; the application never persists secret material.
- Storage definitions map logical names (e.g., `local`) to host paths mounted into the container.

## Deployment Pattern
- The codebase and default configuration live together in this repository.
- Environment-specific configuration stays under `config/` (or another directory you pass through `BACKUP_CONFIG_DIR`); keep secrets in your vault and inject them at runtime via environment variables or mounted files.
- Automation (GitHub Actions, cron, systemd timers) shells out to the compose file in `core-backup` while exporting `BACKUP_CONFIG_DIR`, `BACKUP_DATA_DIR`, and credentials, ensuring secrets never land in Git.

## Data Retention & Observability
- Each job enforces a configurable retention period (default 30 days) by pruning dated backup folders.
- Logs stream to stdout/stderr; optional Slack notifications wire in via `notifications.slack_webhook_env`.
- `manifest.json` records run metadata, artifact locations, and error summaries to simplify restore workflows.

## Extensibility
- New services implement the same connector interface and register with the service factory.
- Storage abstractions already anticipate additional backends (S3, NFS). Implementers should extend `core_backup.storage` while updating validation.
- Shared Docker packaging and CLI mean future connectors can ride the same operational playbook with minimal changes.
