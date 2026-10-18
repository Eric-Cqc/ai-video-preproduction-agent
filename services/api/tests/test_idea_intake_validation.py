"""Intake input must remain convertible to the canonical Brief contract."""

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from foundation_contracts import validate_structured_brief

from services.api.app.application.errors import InvalidRequest
from services.api.app.application.idea_intake_services import (
    _brief_title,
    _parse_structured_output,
    _structured_brief_from_intake,
)
from services.api.app.domain import IdeaIntake, IdeaIntakeStatus


def _fields() -> dict[str, object]:
    return {
        "objective": "目" * 500,
        "platform": "Xiaohongshu",
        "audience": "Commuters",
        "duration_seconds": 30,
        "content_type": "short film",
        "tone": ["warm", " warm ", "cinematic"],
        "key_messages": ["Take a moment"],
        "call_to_action": "Visit tomorrow",
        "constraints": ["Use existing locations", "Use existing locations"],
        "must_include": ["Shop exterior", "Shop exterior"],
        "must_avoid": ["Unproven claims", "Unproven claims"],
        "assumptions": [],
        "missing_fields": ["proof_points", "proof_points"],
    }


def _intake(fields: dict[str, object]) -> IdeaIntake:
    now = datetime.now(UTC)
    return IdeaIntake(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        raw_idea="Synthetic short film",
        status=IdeaIntakeStatus.STRUCTURED,
        brief_id=None,
        brief_version_id=None,
        created_by_actor_subject="actor:owner",
        created_at=now,
        updated_at=now,
        version=1,
        **_parse_structured_output(json.dumps(fields)),
    )


def test_duplicate_intake_items_are_normalized_without_losing_order() -> None:
    intake = _intake(_fields())
    assert intake.tone == ["warm", "cinematic"]
    assert intake.missing_fields == ["proof_points"]
    assert _brief_title(None, intake) == "目" * 200
    content = _structured_brief_from_intake(intake)
    validate_structured_brief(content)
    assert content["objective"] == {
        "primary_goal": "目" * 500,
        "secondary_goals": [],
        "desired_action": "Visit tomorrow",
    }


def test_preexisting_duplicate_items_can_still_be_confirmed() -> None:
    intake = replace(
        _intake(_fields()),
        tone=["warm", "warm"],
        must_include=["Shop", "Shop"],
        must_avoid=["Claims", "Claims"],
        constraints=["Locations", "Locations"],
        missing_fields=["proof_points", "proof_points"],
    )
    original = asdict(intake)
    content = _structured_brief_from_intake(intake)
    validate_structured_brief(content)
    assert _structured_brief_from_intake(intake) == content
    assert asdict(intake) == original


def test_key_messages_fit_the_canonical_joined_text_boundary() -> None:
    fields = {
        **_fields(),
        "tone": [],
        "constraints": [],
        "must_include": [],
        "must_avoid": [],
        "missing_fields": [],
        "key_messages": ["a" * 500, "b" * 498],
    }
    content = _structured_brief_from_intake(_intake(fields))
    validate_structured_brief(content)
    fields["key_messages"] = ["a" * 500, "b" * 499]
    with pytest.raises(InvalidRequest, match="key_messages"):
        _parse_structured_output(json.dumps(fields))
