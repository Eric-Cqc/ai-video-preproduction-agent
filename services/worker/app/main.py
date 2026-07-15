import argparse
import json
import logging
from datetime import UTC, datetime
from typing import Any

from services.worker.app.config import WorkerSettings

SERVICE_NAME = "foundation-worker"
SERVICE_VERSION = "0.1.0"
PRODUCTION_JOB_HANDLERS: tuple[()] = ()


class WorkerJsonFormatter(logging.Formatter):
    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__()
        self.settings = settings

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "environment": self.settings.app_environment,
            "event": getattr(record, "event", record.getMessage()),
            "level": record.levelname,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_worker_logging(settings: WorkerSettings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(WorkerJsonFormatter(settings))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.worker_log_level)


def run_self_check(settings: WorkerSettings) -> dict[str, object]:
    configure_worker_logging(settings)
    logging.getLogger(__name__).info("worker self-check", extra={"event": "worker.self_check"})
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "environment": settings.app_environment,
        "registered_production_job_handlers": len(PRODUCTION_JOB_HANDLERS),
        "production_jobs_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foundation Worker readiness process")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="validate configuration, report readiness, and exit cleanly",
    )
    parser.parse_args(argv)
    result = run_self_check(WorkerSettings())
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0
