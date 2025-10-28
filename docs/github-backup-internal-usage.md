# GitHub Backup Internal Usage

The backup implementation lives in the `github-backup/` directory so we can split it into a standalone public repository (`github-backup`) while continuing to run it from this infrastructure repo.

## Extraction Plan
1. Once the public repository is created, copy the contents of `github-backup/` into it.
2. Publish marketing-friendly documentation in the public repo (the shipped `README.md` is already generic).
3. In this repo, track the public codebase via either:
   - Git submodule: `git submodule add git@github.com:your-org/github-backup.git`.
   - Git subtree or build artifact download during CI/CD.

## Private Deployment
For deployments managed from this repository:
1. Keep the internal configuration (with organization names, secrets, scheduling integration) outside of the `github-backup/` tree. Mount your deployment-specific config at runtime.
2. Use `docker-compose` or host-level scheduling to run the `github-backup` image daily, mounting:
   - `/mnt/backups/github/` to persistent storage.
   - `/opt/github-backup/config/` to your private configuration directory.
3. Store secrets (GitHub tokens, SSH keys) in your secret management solution and inject them as environment variables or short-lived files.

## Customization Hooks
- Additional collectors specific to internal needs can live under `extensions/` in this repo; register them via environment variables before invoking the container.
- Organization-specific documentation (runbooks, restore procedures) should remain in `docs/` here and not be exported to the public repo.

Keep this document updated as we wire the external repository into CI/CD.
