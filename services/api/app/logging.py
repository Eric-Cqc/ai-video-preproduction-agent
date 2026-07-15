import json
import logging
from datetime import UTC, datetime
from typing import Any

from services.api.app.metadata import SERVICE_NAME, SERVICE_VERSION


class JsonLogFormatter(logging.Formatter):
    def __init__(self, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "environment": self.environment,
            "event": getattr(record, "event", record.getMessage()),
            "level": record.levelname,
        }
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Error"
        for field in ("correlation_id", "organization_id", "workspace_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = str(value)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(environment: str, level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter(environment))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
