"""Canonical contracts and pinned inputs survive the offline creative path."""

import json
from pathlib import Path

import pytest
from foundation_contracts import validate_creative_concept, validate_script

from services.api.app.application.model_provider import (
    DeterministicWorkflowProvider,
    ModelRequest,
    ProviderOutcomeStatus,
)

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
)


@pytest.mark.parametrize("duration", [15, 17, 37, 60])
def test_offline_directions_and_script_preserve_pinned_brief(duration: int) -> None:
    brief = json.loads(FIXTURE.read_text())
    brief["deliverables"]["duration_seconds"] = [duration]
    brief["audience"]["language"] = ["zh-CN"]
    provider = DeterministicWorkflowProvider()
    concepts_result = provider.complete(
        ModelRequest("creative_concepts_from_brief", "1.1.0", "", json.dumps(brief), 262144)
    )
    assert concepts_result.status is ProviderOutcomeStatus.SUCCESS
    concepts = json.loads(concepts_result.output_text or "null")
    assert len(concepts) == 3
    assert len({c["title"] for c in concepts}) == 3
    assert len({c["narrative_arc"] for c in concepts}) == 3
    for concept in concepts:
        validate_creative_concept(concept)
        assert concept["key_message"] == brief["creative_constraints"]["required_message"]
        assert concept["assumptions"]
    result = provider.complete(
        ModelRequest(
            "script_from_selected_concept",
            "1.1.0",
            "",
            json.dumps({"concept": concepts[1], "brief": brief}),
            262144,
        )
    )
    script = json.loads(result.output_text or "null")
    validate_script(script)
    assert script["title"] == concepts[1]["title"]
    assert script["target_duration_seconds"] == duration
    assert sum(s["estimated_duration_seconds"] for s in script["scenes"]) == duration
    assert script["call_to_action"] == brief["creative_constraints"]["call_to_action"]
    assert script["language"] == "zh-CN"
    assert script["unresolved_assumptions"]


@pytest.mark.parametrize("text", ["Budget 30,000, no duration", "A 130 second story", "10 秒片段"])
def test_intake_does_not_treat_other_numbers_as_a_supported_duration(text: str) -> None:
    result = DeterministicWorkflowProvider().complete(
        ModelRequest("idea_intake_structuring", "1.0.0", "", text, 262144)
    )
    assert json.loads(result.output_text or "null")["duration_seconds"] is None
