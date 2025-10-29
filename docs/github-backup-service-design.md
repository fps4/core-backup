# GitHub Backup Service Design

## Overview
The GitHub backup service runs inside a Docker container, mirrors repositories, exports metadata, and writes artifacts to a host-mounted directory. It is opinionated toward daily execution but works with any external schedule (cron, systemd timers, GitHub Actions runners).

## Key Responsibilities
- **Repository capture**: Perform `git clone --mirror` into a temporary workspace and package the result as `<repo>_<timestamp>.tar.gz`.
- **Metadata export**: Use the GitHub REST API to export issues, pulls, releases, project boards, teams, members, and optional Actions artifacts into JSON files under `metadata/`.
- **Retention**: Prune dated backup folders beyond the configured retention window (default 30 days).
- **Manifest**: Emit `manifest.json` describing start/end times, artifacts, and any errors for restore triage.

## Execution Flow
1. Load configuration and resolve credentials (`GITHUB_TOKEN`, optional SSH key).
2. Create the run directory `/mnt/backups/github/<YYYY-MM-DD>/` and a metadata subfolder.
3. Determine the target repository set:
   - Use the explicit list when provided.
   - Otherwise enumerate every repository in the configured organization via the GitHub API.
4. For each repository, mirror the git data, package archives, and fetch metadata.
5. Optionally export organization-wide resources when enabled.
6. Enforce retention, write the manifest, and exit with status `0`, `1`, or `2` based on success.

## Configuration Highlights
```yaml
github:
  organization: your-org
  auth:
    token_env: GITHUB_TOKEN
  retention_days: 30
  repositories: []          # empty list => discover all repos automatically
  organization_exports:
    members: true
    teams: true
storage:
  base_path: /mnt/backups/github
logging:
  level: info
notifications:
  slack_webhook_env: SLACK_BACKUP_WEBHOOK
```
- Secrets should be supplied via environment variables or injected files, not committed to Git.
- When providing an explicit `repositories` list, per-repo flags (`include_wiki`, `include_projects`, etc.) tailor export scope.
- The Docker Compose file binds configuration from `BACKUP_CONFIG_DIR` (defaults to `${repo_root}/config`) and backups from `BACKUP_DATA_DIR`.

## Scheduling Patterns
- **Cron/systemd on infrastructure hosts**: invoke the compose files in this repo from a wrapper script that exports `BACKUP_CONFIG_DIR`, `BACKUP_DATA_DIR`, and credentials.
- **GitHub Actions self-hosted runners**: use the provided workflow (`.github/workflows/deploy.yml`) to trigger Docker Compose on runner labels.
- **Kubernetes**: wrap the image in a CronJob manifest mounting persistent storage at `/mnt/backups/github`.

## Security & Compliance
- Scope the GitHub token for read-only access to repos, metadata, and Actions artifacts as needed.
- Mount configuration read-only; keep backup storage on encrypted volumes.
- Ensure network egress controls match organizational policy; the container only needs outbound access to GitHub APIs.

## Restore Considerations
- Extract repository archives and run `git clone` against the bare mirror to recover history.
- Replay metadata exports as needed; they are JSON payloads aligned with the REST API responses.
- Use `manifest.json` to identify failed repositories or missing artifacts before beginning a restore.
