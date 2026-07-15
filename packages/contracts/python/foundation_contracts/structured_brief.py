import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

STRUCTURED_BRIEF_SCHEMA_VERSION = "1.0.0"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "structured-brief-v1.schema.json"


@lru_cache(maxsize=1)
def load_structured_brief_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    return schema


def validate_structured_brief(value: object) -> None:
    Draft7Validator(load_structured_brief_schema()).validate(value)
