# Publishing & Maintaining `core-backup`

This repository is now the public home for the GitHub backup service. Use the steps below to keep the public code clean while running production deployments from the private configuration repository.

## Public Repository Checklist
1. Keep sensitive information (org names, tokens, schedules) out of the tree. The sample configs in `config/` must remain generic.
2. Update documentation (`README.md`, `docs/`) when operational guidance changes. Highlight that real configs live in `project-core-backup`.
3. Tag releases (`v1.x.y`) whenever significant behavior changes so downstream automation can pin known-good versions.

## Private Configuration Repository (`project-core-backup`)
1. Store runtime configuration under `config/` (e.g., `github-backup.yaml`) plus any wrapper scripts or workflows needed by operators.
2. Reference this repository as a git submodule or regular sibling checkout. The default Docker Compose file assumes a sibling at `../project-core-backup`.
3. Define deployment automation (cron jobs, GitHub Actions workflows) inside the private repo. Each job should:
   ```bash
   BACKUP_CONFIG_DIR=$(pwd)/config \
   BACKUP_DATA_DIR=/srv/backups/github \
   docker compose -f ../core-backup/docker/compose.yaml \
                  -f ../core-backup/docker/compose.prod.yaml up -d --build
   ```
4. Keep secrets in your chosen secret manager and inject them through environment variables or Docker secrets at runtime.

## Syncing Code Changes
1. Develop features in `core-backup` as usual and open pull requests.
2. After merging, bump the release tag if necessary and notify operators so they can pull the latest code.
3. In `project-core-backup`, update the submodule reference or run `git pull` (if using a plain checkout) to align with the new release.

## Communications & Marketing
- Use the public repo’s Issues/Discussions for community-facing questions.
- Maintain internal runbooks in the private repo (`docs/` there) when they contain sensitive details or environment-specific instructions.
