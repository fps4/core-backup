# GitHub Daily Backup Service Design

## Overview
The GitHub Daily Backup Service runs inside a local Docker container and copies repository assets to the Docker host at `/mnt/backups/github/`. Each execution creates a timestamped backup package per repository and supporting data so restorations are straightforward. A retention policy removes backups older than 30 days. The design is modular and can be extended to additional SaaS sources beyond GitHub.

## Goals
- Back up selected GitHub repositories, Projects, Releases, Issues, Pull Requests, and metadata daily.
- Store each backup under `/mnt/backups/github/<ISO-8601-date>/` with compressed archives for repositories and structured exports for metadata.
- Enforce a 30-day retention window.
- Provide a human-readable YAML configuration that lists repositories and options.
- Keep the solution extensible for additional services (e.g., GitLab, Bitbucket, Jira) with minimal redesign.

## Non-Goals
- Real-time mirroring or incremental backups beyond daily cadence.
- Managing GitHub Enterprise Server infrastructure.
- Providing a full disaster-recovery plan for restoring to GitHub; the focus is repository data preservation.

## High-Level Architecture
- **Scheduler**: Triggers the backup container daily at a defined time (e.g., systemd timer, cron job, or Docker Scheduled Jobs).
- **Backup Container**: Single Docker image responsible for running the backup workflow; mounts two host directories:
  - `/mnt/backups/github/` (read/write) for storing artifacts.
  - `/opt/github-backup/config/` (read-only) containing the YAML configuration and credentials.
- **Collectors**: Modular scripts or binaries inside the container to gather different data types (repositories, Projects, metadata).
- **Archiver**: Compresses each repository mirror (`git clone --mirror`) and exports metadata to JSON/ndjson or CSV files.
- **Retention Manager**: Removes directories older than 30 days, logging deletions for auditability.
- **Logging & Metrics**: Writes execution logs to stdout (captured by Docker) and optionally pushes metrics/events to a host collector.

```
┌─────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│ Host Cron   │  -->  │ Backup Docker Image │  -->  │ /mnt/backups/github/ │
└─────────────┘       │  Collectors &       │       │ yyyy-mm-dd/          │
                       │  Retention Manager │       │   repoA.tar.gz       │
                       └──────────────────────┘       │   repoB.tar.gz       │
                                                      │   metadata/          │
                                                      └──────────────────────┘
```

## Backup Workflow
1. **Initialization**
   - Container starts, loads config YAML, resolves credentials (PAT, SSH keys, API tokens).
   - Creates working directory `/mnt/backups/github/<YYYY-MM-DD>/`.
2. **Repository Archive**
   - For each repository listed in config:
     - Run `git clone --mirror` (first run) or `git remote update` (subsequent runs) into a temp workspace.
     - Generate `repo-name_<timestamp>.tar.gz` containing bare mirror plus metadata such as default branch and latest commit.
3. **Metadata Export**
   - Collect issues, PRs, releases, project boards, workflows, environments, and secrets metadata via GitHub REST or GraphQL API.
   - Save as JSON inside `metadata/` folder, e.g., `metadata/repo-name/issues.json`.
   - Optionally export Markdown or CSV for easier manual inspection.
4. **Organization-level Artifacts (Optional)**
   - If configured, export organization Projects, members, teams, and settings to separate archives.
5. **Retention Enforcement**
   - Enumerate existing directories under `/mnt/backups/github/`, delete any older than 30 days, and log action.
6. **Completion**
   - Generate manifest file summarizing artifacts (`manifest.json`).
   - Emit metrics/log summary (duration, success/failure counts).

## Configuration
The container reads a YAML configuration file mounted read-only, e.g., `/opt/github-backup/config/github-backup.yaml`.

### Sample YAML
```yaml
github:
  organization: your-org-name
  auth:
    token_env: GITHUB_TOKEN           # Environment variable name loaded by entrypoint
    ssh_key_path: /secrets/github_id_rsa
  schedule:
    cron: "0 3 * * *"                 # Container-embedded cron; optional if host schedules
  retention_days: 30
  repositories:
    - name: backend-repo
      include_wiki: true
      include_releases: true
      include_projects: true
    - name: data-pipeline
      include_submodules: true
      include_artifacts: false
  organization_exports:
    members: true
    teams: true
    projects: true
  include_actions_artifacts: false     # Large; default off
storage:
  base_path: /mnt/backups/github       # Host path mounted into container
logging:
  level: info
  emit_metrics: true
notifications:
  slack_webhook_env: SLACK_BACKUP_WEBHOOK
```

### Config Principles
- Use environment variables for secrets; never store tokens directly in YAML.
- Each service (GitHub, GitLab, etc.) gets its own section, enabling future extensions.
- Flags enable/disable specific data collectors so we can fine-tune backups per repo.

## Docker Image Responsibilities
- Provide runtime (Python/Go/Node) plus CLI tools:
  - `git`, `gh` CLI, or custom API client.
  - `tar`, `gzip`, `jq` (for JSON shaping).
- Entrypoint script:
  - Parses YAML config.
  - Runs collectors sequentially (or via job queue).
  - Handles non-zero exit codes and surfaces errors.
- Optional multi-stage build to keep runtime lightweight.

## Scheduling Options
- **Host Cron**: `docker run --rm ... backup-image` executed daily.
- **Docker Scheduled Jobs**: Use Docker's built-in scheduling or an orchestrator (e.g., Docker Swarm, ECS).
- **Kubernetes CronJob**: Reuse image in cluster; mount NFS path at `/mnt/backups/github/`.
Each option should honor the 30-day retention logic inside the container to keep behavior consistent.

## Retention Strategy
- Determine "cutoff date" as `today - retention_days`.
- For each folder in `/mnt/backups/github/`, parse folder name as date and delete if older than cutoff.
- Retention respects metadata stored alongside repositories (manifest, logs).
- Optional dry-run mode for verifying deletions.

## Observability & Alerting
- Write structured logs (JSON) to stdout; host log collector can aggregate.
- Emit metrics: total repos processed, failures, runtime. Expose via text file or push gateway.
- Optional Slack/email notification using webhook defined in config.
- Failure handling: exit with non-zero code and include failure counts in manifest.

## Security Considerations
- Scope GitHub token with least privilege (read-only repository and metadata).
- Store secrets using Docker secrets or host-level secret management.
- Ensure `/mnt/backups/github/` resides on encrypted storage.
- Validate repository names to prevent path traversal.

## Extensibility for Other Services
- Design collectors as pluggable modules keyed by service type.
- Configuration supports multiple service blocks (e.g., `gitlab:`) sharing the same retention engine.
- Abstract storage writer and retention manager so they are service-agnostic.
- Provide reusable manifest schema capturing service, resource type, and object count.

## Restore Process (High Level)
- Select date directory under `/mnt/backups/github/`.
- For repositories: `tar -xzf repo-name_<timestamp>.tar.gz` and run `git clone` from bare mirror.
- For metadata: ingest JSON exports or import into target system via API scripts.
- Manifest file lists available assets and command hints for restoration.

## Open Questions
- Should we capture Git LFS objects separately? No
- Do we need encryption at rest for individual tarballs? No
- How to version schema of metadata exports for future compatibility? Adopt semantic versioning (start at `1.0.0`) embedded in each manifest and metadata payload header, incrementing minor versions for additive fields and major versions for breaking structure changes.

## Next Steps
- Finalize collector implementation language and libraries.
- Build Docker image and entrypoint script.
- Implement automated tests (unit/integration) for collectors and retention logic.
- Configure host scheduling and monitoring integrations.
