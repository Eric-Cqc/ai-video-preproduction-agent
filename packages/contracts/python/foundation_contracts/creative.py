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
    _validate_storyboard_semantics(value)


def validate_shot_plan(value: object) -> None:
    Draft7Validator(_schema("shot-plan-v1.schema.json")).validate(value)
    _validate_sequence(value, "shots", "shot_number")
    _validate_shot_plan_semantics(value)
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


def _validate_storyboard_semantics(value: object) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("scenes"), list):
        return
    scenes = value["scenes"]
    source_numbers = [
        item.get("source_script_scene_number") for item in scenes if isinstance(item, dict)
    ]
    if source_numbers != list(range(1, len(scenes) + 1)):
        raise ValueError("source_script_scene_number values must be contiguous")
    total = 0
    for item in scenes:
        if not isinstance(item, dict):
            continue
        duration = item.get("estimated_duration_seconds")
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            raise ValueError("storyboard scene duration must be a positive integer")
        total += duration
        for field in ("visual_summary", "composition", "camera_language", "action"):
            text = item.get(field)
            if isinstance(text, str) and _contains_external_action(text):
                raise ValueError("visual planning content contains an external-action instruction")
    if total <= 0:
        raise ValueError("storyboard total duration must be positive")


def _validate_shot_plan_semantics(value: object) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("shots"), list):
        return
    shots = value["shots"]
    scene_numbers = [
        item.get("storyboard_scene_number") for item in shots if isinstance(item, dict)
    ]
    if not scene_numbers:
        return
    if any(not isinstance(number, int) or isinstance(number, bool) for number in scene_numbers):
        raise ValueError("shot scene references must be integers")
    if any(isinstance(number, int) and number < 1 for number in scene_numbers):
        raise ValueError("shot scene references must be positive")
    shot_ids = [item.get("shot_id") for item in shots if isinstance(item, dict)]
    if len(shot_ids) != len(set(shot_ids)):
        raise ValueError("shot_id values must be unique")
    for item in shots:
        if not isinstance(item, dict):
            continue
        if _contains_external_action(str(item.get("generation_prompt", ""))):
            raise ValueError("generation prompt contains an external-action instruction")


def _contains_external_action(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "http://",
            "https://",
            "fetch ",
            "tool call",
            "run shell",
            "execute ",
            "ignore previous",
            "system prompt",
        )
    )
