# Core Backup Platform Solution Design

## Context
`core-backup` aims to provide a unified automation layer for snapshot-style backups across SaaS APIs and self-hosted services. Today the repository focuses on GitHub exports, but the product direction is to support additional targets such as MongoDB, Docker volumes, and other developer tooling. Backups are orchestrated via YAML-defined jobs so teams can declaratively opt-in without bespoke scripting.

## Goals
- Offer a single runtime image/CLI that can execute multiple backup job types in one invocation.
- Let operations teams define backup jobs declaratively in YAML, including scheduling hints and retention policies.
- Reuse shared concerns (logging, notifications, storage adapters, retention, manifests) across all service integrations.
- Keep collectors pluggable so we can add new services with bounded effort and consistent configuration.
- Run reliably in containerized environments (Docker/Kubernetes) with minimal external dependencies.

## Non-Goals
- Orchestrating real-time replication or streaming backups.
- Managing restore workflows end-to-end; we focus on producing restorable artifacts.
- Acting as a full-featured backup scheduling platform (e.g., replacing cron/Kubernetes CronJobs).
- Providing a SaaS control plane; the solution is operator-run.

## Architectural Overview
The platform is structured as a Python package composed of four layers:

1. **Entry Orchestrator**  
   Parses configuration, resolves secrets, dispatches jobs, aggregates results, and applies retention. Runs once per scheduled execution inside a container or CLI environment.

2. **Job Engine**  
   Represents each backup job as a `BackupJob` instance with lifecycle hooks (`prepare`, `run`, `finalize`). The engine enforces sequencing, parallelism limits, retries, and common error handling.

3. **Service Connectors**  
   Pluggable modules implementing the `BackupService` protocol. Each connector owns data collection logic, temporary workspace management, and artifact production. Examples: `github`, `mongodb`, `docker_volume`.

4. **Shared Services**  
   Cross-cutting utilities for logging, metrics, notifications, artifact storage abstraction, retention pruning, manifest generation, and checksum validation.

```
┌───────────────────────────┐
│         Entrypoint        │
│  - parse config           │
│  - schedule jobs          │
│  - retention & reporting  │
└───────────┬───────────────┘
            │ uses
┌───────────▼───────────┐        ┌─────────────────────┐
│       Job Engine       │<------│  Notifications &    │
│  - lifecycle control   │       │  Observability      │
└───────────┬───────────┘        └─────────────────────┘
            │ dispatches
┌───────────▼───────────┐
│  Service Connectors   │
│ (GitHub, MongoDB,…)   │
└───────────┬───────────┘
            │ emits
┌───────────▼───────────┐
│   Storage Adapters     │
│ (local FS, S3, NFS)    │
└────────────────────────┘
```

## Configuration Model
- Top-level YAML file lists one or more `jobs`. Each job references a `service` type, job-specific settings, retention policy, and execution hints.
- Secrets are referenced via indirection (`env`, `file`, or `vault` lookup). The entrypoint resolves them before job execution.
- Common fields:
  ```yaml
  jobs:
    - name: github-org-backup
      service: github
      schedule: 0 3 * * *
      retention_days: 30
      target_storage: local
      options:
        organization: my-org
        repositories: [...]
    - name: mongo-prod-backup
      service: mongodb
      retention_days: 14
      target_storage: s3
      options:
        uri_env: MONGO_URI
        databases:
          - name: app
            dump_strategy: mongodump
  storage:
    local:
      type: filesystem
      base_path: /mnt/backups
    s3:
      type: s3
      bucket_env: S3_BUCKET
      prefix: backups/
  notifications:
    slack:
      webhook_env: SLACK_WEBHOOK
  ```
- Validation is handled via Pydantic models to deliver precise error reporting.
- Schedule hints are advisory. Actual scheduling is handled by the host (cron, Kubernetes). The entrypoint can optionally run an embedded APScheduler for standalone use.

## Execution Flow
1. **Bootstrap**
   - Load YAML config and coerce into Python models.
   - Resolve secrets and initialize logging/metrics sinks.
   - Instantiate storage adapters (filesystem, S3, etc.).
2. **Job Selection**
   - Determine which jobs should run in the current invocation (e.g., all jobs, a subset based on CLI flags, or schedule match).
3. **Job Execution**
   - For each job, acquire a workspace (tmpdir) and call service connector lifecycle.
   - Collect primary data (e.g., repository mirrors, `mongodump`, Docker volume tarballs).
   - Stream artifacts to storage adapter; produce checksum and manifest entries.
4. **Retention & Verification**
   - Run retention policy per job using storage adapter listing APIs.
   - Optionally verify integrity (checksum spot-checks).
5. **Reporting**
   - Persist a structured manifest (`manifest.json`) summarizing artifacts, durations, item counts, and warnings.
   - Emit metrics (Prometheus textfile or Pushgateway).
   - Trigger notifications on success/failure, including actionable error summaries.

## Service Connector Responsibilities
- Implement `prepare(context)` to validate options and set up clients (e.g., GitHub API session, Mongo client, Docker SDK).
- Implement `execute(context)` to produce artifacts. Return metadata describing artifact paths, counts, and custom fields.
- Implement `cleanup(context)` for temp workspace disposal.
- Connectors share utility modules (e.g., rate limiter, retry helpers). They should avoid writing directly to final storage; instead, they stream through storage adapters to enforce consistent naming and checksum behavior.

### Example Connectors
- **GitHub**: Reuse existing `github_backup` functionality; refactor into connector abiding by new interfaces. Supports repository mirrors, metadata exports, org-level data.
- **MongoDB**: Wrap `mongodump` binary (executed inside container) or use `pymongo` to stream dumps. Supports per-database or per-collection filters; supports oplog capture optional.
- **Docker Volume**: Use `docker` SDK to snapshot named volumes or bind mounts by tarballing their mountpoints, optionally pausing containers.
- **Generic Filesystem**: Provide `rsync`/`tar`-based backup for arbitrary paths as initial stub.

## Storage & Retention
- **Storage Adapters** abstract artifact persistence. Initial adapter targets local filesystem (host-mounted path). Future adapters include S3-compatible storage and NFS exports.
- Directory schema: `<storage>/<job_name>/<YYYY-MM-DD>/<artifact>`.
- Retention uses adapter APIs to list dated folders and delete beyond threshold. Deletion events are logged with resource identifiers.
- Optional retention modes: `count`, `age`, `hybrid`.

## Observability & Notifications
- Structured JSON logs with correlation IDs per job.
- Metrics: job duration, artifact counts, bytes written, errors. Export via Prometheus textfile or StatsD.
- Notification providers: Slack webhook, email (SMTP), PagerDuty. Config-driven thresholds (notify on failure, on success, or on threshold breach).
- Manifests stored alongside artifacts for audit and restore guidance.

## Security Considerations
- Minimal runtime (Python slim + required CLIs). Container built with non-root user.
- Secrets injected via env vars or mounted files; never persisted to manifests/logs.
- Optional client-side encryption (age/GPG) prior to writing to storage adapter.
- Provide network egress controls (no outbound Internet where not needed). Ensure connectors support HTTP proxy configuration for compliance.

## Error Handling & Resilience
- Connector errors are scoped to their job unless flagged as fatal (e.g., configuration invalid). Jobs fail independently; orchestrator summarizes global status.
- Retries with exponential backoff for transient API failures (GitHub HTTP 5xx, network timeouts).
- Partial success is captured in manifest with detailed error codes for follow-up.
- Exit codes: `0` success, `1` completed with job-level failures, `2` configuration or orchestrator failure.

## Testing Strategy
- Unit tests for config parsing, storage adapters, retention logic, and connector interfaces.
- Service-specific integration tests run behind feature flags (e.g., use GitHub mock server, local Mongo container).
- Golden manifest snapshots ensure schema stability.
- Smoke test script executes full run against docker-compose stack (Mongo + mock Git service) inside CI.

## Language Choice Justification
- Python remains the primary implementation language.
  - Existing GitHub tooling is already Python-based, enabling code reuse.
  - Rich ecosystem for YAML parsing, API clients, and CLI invocation.
  - Fast iteration and readability for ops-focused teams.
  - Extensive library support for MongoDB (`pymongo`), Docker (`docker` SDK), cloud storage (boto3), and scheduling.
- Performance-sensitive components (e.g., large file streaming) delegate to external binaries (`git`, `mongodump`, `tar`), minimizing Python overhead.
- If future connectors demand stronger parallelism or binary streaming performance, we can integrate subprocess workers or isolate them in Rust/Go extensions while keeping Python as orchestrator glue.

## Roadmap
1. Refactor existing GitHub implementation into connector-based architecture.
2. Implement configuration loader and job engine abstractions.
3. Introduce filesystem storage adapter with retention module reuse.
4. Add MongoDB connector (mongodump-based) and Docker volume connector.
5. Extend CLI/entrypoint to support targeted job execution and dry-run mode.
6. Wire Slack notifications and Prometheus metrics exporter.
7. Hardening: integration tests, documentation updates, sample configs for new services.

## Deliverables
- Updated package structure under `core_backup/` with shared modules and service connectors.
- Container image bundling Python runtime plus required CLIs (`git`, `mongodump`, `docker` client).
- Updated documentation and example YAML configs under `docs/` and `config/`.
- CI workflows executing unit + smoke tests and optionally publishing container images.

