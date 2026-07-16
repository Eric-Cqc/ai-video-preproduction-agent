import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

CREATIVE_CONCEPT_SCHEMA_VERSION = "1.0.0"
SCRIPT_SCHEMA_VERSION = "1.0.0"
STORYBOARD_SCHEMA_VERSION = "1.0.0"
SHOT_PLAN_SCHEMA_VERSION = "1.0.0"


@lru_cache(maxsize=4)
def _schema(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(value)
    return value


def validate_creative_concept(value: object) -> None:
    Draft7Validator(_schema("creative-concept-v1.schema.json")).validate(value)


def validate_script(value: object) -> None:
    Draft7Validator(_schema("script-v1.schema.json")).validate(value)
    _validate_sequence(value, "scenes", "scene_number")


def validate_storyboard(value: object) -> None:
    Draft7Validator(_schema("storyboard-v1.schema.json")).validate(value)
    _validate_sequence(value, "scenes", "storyboard_scene_number")


def validate_shot_plan(value: object) -> None:
    Draft7Validator(_schema("shot-plan-v1.schema.json")).validate(value)
    _validate_sequence(value, "shots", "shot_number")
    if isinstance(value, dict):
        for shot in value["shots"]:
            if isinstance(shot, dict):
                prompt = str(shot["generation_prompt"]).lower()
                if any(
                    token in prompt
                    for token in ("http://", "https://", "fetch ", "tool call", "run shell")
                ):
                    raise ValueError("generation prompt contains an external-action instruction")


def _validate_sequence(value: object, key: str, number_key: str) -> None:
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        return
    items = value[key]
    numbers = [item.get(number_key) for item in items if isinstance(item, dict)]
    if numbers != list(range(1, len(items) + 1)):
        raise ValueError(f"{number_key} values must be contiguous")
