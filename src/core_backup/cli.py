from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from github_backup.logger import configure_logging

from .config import ConfigurationError, CoreConfig, load_config
from .orchestrator import BackupOrchestrator
from .services import create_service

DEFAULT_CONFIG_PATH = "/opt/core-backup/config/core-backup.yaml"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Core Backup orchestrator CLI.")
    parser.add_argument(
        "--config",
        default=os.getenv("CORE_BACKUP_CONFIG", DEFAULT_CONFIG_PATH),
        help="Path to configuration YAML file.",
    )
    parser.add_argument(
        "--job",
        action="append",
        help="Specific job name to run (can be specified multiple times). Runs all jobs when omitted.",
    )
    parser.add_argument(
        "--list-jobs",
        action="store_true",
        help="List jobs defined in the configuration and exit.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Log level (default INFO).",
    )
    return parser.parse_args(argv)


def load_configuration(path: Path) -> CoreConfig:
    try:
        return load_config(path)
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc


def list_jobs(config: CoreConfig) -> None:
    for job in config.jobs:
        print(job.name)


def run_jobs(config: CoreConfig, job_names: Optional[List[str]]) -> int:
    orchestrator = BackupOrchestrator(config=config, service_factory=create_service)
    results = orchestrator.run(job_names)
    success = True

    for result in results:
        if result.success:
            logging.info(
                "Job %s succeeded in %.2fs",
                result.job_name,
                (result.completed_at - result.started_at).total_seconds(),
            )
        else:
            success = False
            logging.error("Job %s failed: %s", result.job_name, "; ".join(result.errors))

    return 0 if success else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    config_path = Path(args.config).expanduser()
    config = load_configuration(config_path)

    if args.list_jobs:
        list_jobs(config)
        return 0

    job_names = args.job if args.job else None
    return run_jobs(config, job_names)


if __name__ == "__main__":
    sys.exit(main())
