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
RUN mkdir -p /opt/core-backup/config
COPY config/core-backup.yaml.example /opt/core-backup/config/core-backup.yaml

ENV PYTHONPATH=/app/src \
    CORE_BACKUP_CONFIG=/opt/core-backup/config/core-backup.yaml \
    LOG_LEVEL=INFO

ENTRYPOINT ["python", "-m", "core_backup.cli"]
