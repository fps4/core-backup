# Publishing `github-backup`

Use these steps to extract, publish, and keep the public `github-backup` repository in sync with this infrastructure repo.

## 1. Prepare Local Copy
```bash
cd /path/to/core-services
tar -czf /tmp/github-backup.tar.gz github-backup
```
or simply copy the `github-backup/` directory into a clean workspace.

## 2. Initialize Public Repository
```bash
mkdir github-backup-public && cd github-backup-public
cp -R /path/to/github-backup/* .
git init
git add .
git commit -m "Initial public release"
gh repo create your-org/github-backup --public --source=. --remote=origin --push
```
Replace `your-org` with the actual GitHub organization or username. The repo ships with a MIT license, generic README, and sample configuration ready for marketing/documentation.

## 3. Link Back Internally
Decide how this infrastructure repo consumes the public project:
- **Git submodule**: `git submodule add git@github.com:your-org/github-backup.git github-backup`
- **Git subtree**: `git subtree add --prefix=github-backup git@github.com:your-org/github-backup.git main --squash`

## 4. Ongoing Updates
1. Make improvements in a feature branch of the public repo.
2. Tag releases (e.g., `v1.0.0`) so internal pipelines can pin versions.
3. Pull updates into this repo via the chosen linkage (submodule/subtree) or by downloading release artifacts in CI/CD.

## 5. Marketing Content
The public README is neutral and marketing-friendly. Add blog posts, badges, or screenshots as desired in that repository without exposing private infrastructure details.
