from datetime import UTC, datetime
from uuid import uuid4

import pytest

from services.api.app.domain import Brief, BriefStatus, InvalidBriefTransition, VersionConflict
from services.api.app.domain.brief_issues import detect_requirement_issues


def brief() -> Brief:
    now = datetime.now(UTC)
    return Brief(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        title="Campaign Brief",
        status=BriefStatus.DRAFT,
        current_version_id=uuid4(),
        latest_version_number=1,
        created_by_actor_subject="actor:owner",
        created_at=now,
        updated_at=now,
        version=1,
    )


def test_brief_lifecycle_and_version_guard() -> None:
    current = brief()
    submitted = current.submit(expected_version=1, now=datetime.now(UTC))
    approved = submitted.approve(expected_version=2, now=datetime.now(UTC))
    assert approved.status is BriefStatus.APPROVED
    assert approved.version == 3
    with pytest.raises(VersionConflict):
        current.submit(expected_version=2, now=datetime.now(UTC))
    with pytest.raises(InvalidBriefTransition):
        current.approve(expected_version=1, now=datetime.now(UTC))


def test_deterministic_checker_has_only_declared_checks() -> None:
    issues = detect_requirement_issues(
        {
            "objective": {"primary_goal": None},
            "audience": {"primary_audience": ""},
            "creative_constraints": {"call_to_action": None},
            "deliverables": {"duration_seconds": [15, 30]},
            "legal_and_compliance": {
                "regulated_category": "financial_services",
                "disclaimer_requirements": [],
            },
        }
    )
    assert {issue.field_path for issue in issues} == {
        "objective.primary_goal",
        "audience.primary_audience",
        "creative_constraints.call_to_action",
        "deliverables.duration_seconds",
        "legal_and_compliance.disclaimer_requirements",
    }
    assert all(issue.severity.value == "blocking" for issue in issues)
