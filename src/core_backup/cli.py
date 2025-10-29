from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from croniter import croniter
from github_backup.logger import configure_logging
from zoneinfo import ZoneInfo

from .config import ConfigurationError, CoreConfig, SchedulerConfig, load_config
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


def load_configuration(path: Path, *, exit_on_error: bool = True) -> CoreConfig:
    try:
        return load_config(path)
    except ConfigurationError as exc:
        if exit_on_error:
            raise SystemExit(f"Configuration error: {exc}") from exc
        raise


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
    if config.scheduler:
        return run_with_scheduler(
            config_path=config_path,
            initial_config=config,
            job_names=job_names,
        )
    return run_jobs(config, job_names)


def run_with_scheduler(
    config_path: Path,
    initial_config: CoreConfig,
    job_names: Optional[List[str]],
) -> int:
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: Optional[object]) -> None:
        logging.info("Received signal %s; stopping scheduler", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    config = initial_config
    scheduler = _require_scheduler(config.scheduler)
    timezone = ZoneInfo(scheduler.timezone)
    next_run = datetime.now(timezone) if scheduler.run_on_startup else _next_run(scheduler.cron, datetime.now(timezone))

    if scheduler.run_on_startup:
        logging.info("Executing initial run immediately")
    else:
        logging.info("Next run scheduled for %s", next_run.isoformat())

    while not stop_event.is_set():
        now = datetime.now(timezone)
        if now >= next_run:
            try:
                config = load_configuration(config_path, exit_on_error=False)
            except ConfigurationError as exc:
                logging.error("Failed to reload configuration: %s; continuing with previous settings", exc)
            else:
                if not config.scheduler:
                    logging.info("Scheduler removed from configuration; exiting loop")
                    break
                scheduler = _require_scheduler(config.scheduler)
                timezone = ZoneInfo(scheduler.timezone)

            exit_code = run_jobs(config, job_names)
            if exit_code != 0:
                logging.warning("Scheduled run completed with errors (exit code %s)", exit_code)

            next_run = _next_run(scheduler.cron, datetime.now(timezone))
            logging.info("Next run scheduled for %s", next_run.isoformat())
            continue

        sleep_for = max((next_run - now).total_seconds(), 0)
        stop_event.wait(min(sleep_for, 60))

    logging.info("Scheduler stopped")
    return 0


def _require_scheduler(scheduler: Optional[SchedulerConfig]) -> SchedulerConfig:
    if not scheduler:
        raise ValueError("Scheduler configuration is required")
    return scheduler


def _next_run(cron_expression: str, reference: datetime) -> datetime:
    return croniter(cron_expression, reference).get_next(datetime)


if __name__ == "__main__":
    sys.exit(main())
