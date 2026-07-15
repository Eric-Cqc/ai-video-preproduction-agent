from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from services.api.app.domain import (
    InvalidProjectMutation,
    InvalidProjectTransition,
    Project,
    ProjectStatus,
    VersionConflict,
)

NOW = datetime(2026, 7, 15, tzinfo=UTC)


def project(status: ProjectStatus = ProjectStatus.DRAFT, version: int = 1) -> Project:
    return Project(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        name="Foundation Project",
        description=None,
        status=status,
        created_by_actor_subject="actor:test",
        created_at=NOW,
        updated_at=NOW,
        version=version,
    )


def test_valid_lifecycle_transitions_increment_version_once() -> None:
    active = project().activate(expected_version=1, now=NOW + timedelta(seconds=1))
    archived = active.archive(expected_version=2, now=NOW + timedelta(seconds=2))
    assert active.status is ProjectStatus.ACTIVE
    assert active.version == 2
    assert archived.status is ProjectStatus.ARCHIVED
    assert archived.version == 3


def test_invalid_lifecycle_transition_is_rejected() -> None:
    with pytest.raises(InvalidProjectTransition):
        project(ProjectStatus.ACTIVE).activate(expected_version=1, now=NOW)
    with pytest.raises(InvalidProjectTransition):
        project(ProjectStatus.ARCHIVED).archive(expected_version=1, now=NOW)


def test_stale_version_is_rejected_without_mutation() -> None:
    original = project(version=2)
    with pytest.raises(VersionConflict):
        original.activate(expected_version=1, now=NOW)
    assert original.status is ProjectStatus.DRAFT
    assert original.version == 2


def test_project_patch_is_constrained() -> None:
    updated = project().update_details(
        expected_version=1,
        changed_fields=frozenset({"description"}),
        name=None,
        description="A scoped persistence proof",
        now=NOW + timedelta(seconds=1),
    )
    assert updated.description == "A scoped persistence proof"
    assert updated.version == 2
    with pytest.raises(InvalidProjectMutation):
        updated.update_details(
            expected_version=2,
            changed_fields=frozenset(),
            name=None,
            description=None,
            now=NOW,
        )


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError):
        ProjectStatus("rendering")
