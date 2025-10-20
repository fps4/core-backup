FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        ca-certificates \
        jq \
        tar \
        gzip && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PYTHONPATH=/app/src \
    CONFIG_PATH=/opt/github-backup/config/github-backup.yaml \
    STORAGE_BASE_PATH=/mnt/backups/github \
    LOG_LEVEL=INFO

ENTRYPOINT ["python", "-m", "fps_github_backup.entrypoint"]
