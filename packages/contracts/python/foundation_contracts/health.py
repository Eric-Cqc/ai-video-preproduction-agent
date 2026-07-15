import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

HEALTH_CONTRACT_VERSION = "1.0.0"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "health-v1.schema.json"


@lru_cache(maxsize=1)
def load_health_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    return schema


def validate_health_response(value: object) -> None:
    Draft7Validator(load_health_schema()).validate(value)
