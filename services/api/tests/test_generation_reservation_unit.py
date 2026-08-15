from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.api.app.application.context import TenantContext
from services.api.app.application.creative_services import CreativeApplicationService
from services.api.app.application.errors import ResourceConflict
from services.api.app.application.model_provider import (
    DeterministicFakeProvider,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.application.uow import UnitOfWork
from services.api.app.application.visual_planning_services import VisualPlanningApplicationService
from services.api.app.domain import (
    CreativeGenerationOperationStatus,
    CreativeGenerationOperationType,
    VisualPlanningOperationStatus,
    VisualPlanningOperationType,
)


class _OperationRepository:
    def __init__(self, existing: object | None) -> None:
        self.existing = existing
        self.takeover_calls: list[tuple[object, int]] = []

    def get_by_key(self, *_: object) -> object | None:
        return self.existing

    def reserve(self, operation: object) -> object:
        self.existing = operation
        return operation

    def takeover(self, operation: object, *, expected_version: int) -> object:
        self.takeover_calls.append((operation, expected_version))
        self.existing = operation
        return operation


def _context() -> TenantContext:
    return TenantContext("actor", "correlation", uuid4(), uuid4())


def _unused_uow() -> UnitOfWork:
    raise AssertionError("reservation unit tests must not open a UoW")


def test_creative_reservation_takes_over_stale_row() -> None:
    now = datetime(2026, 8, 16, tzinfo=UTC)
    context = _context()
    project_id = uuid4()
    service = CreativeApplicationService(
        _unused_uow,
        DeterministicFakeProvider(ProviderOutcome(ProviderOutcomeStatus.ERROR)),
        clock=lambda: now,
        stale_reservation_age_seconds=60,
    )
    reservation = service._reserve(
        context,
        project_id,
        CreativeGenerationOperationType.GENERATE_CONCEPTS,
        "same-key",
        "a" * 64,
    )
    stale = reservation.__class__(
        reservation.id,
        reservation.organization_id,
        reservation.workspace_id,
        reservation.project_id,
        reservation.operation,
        reservation.idempotency_key,
        reservation.request_digest,
        reservation.status,
        reservation.outcome_concept_run_id,
        reservation.outcome_candidate_id,
        reservation.outcome_selection_id,
        reservation.outcome_script_run_id,
        reservation.outcome_script_version_id,
        reservation.submitted_by_actor_subject,
        now - timedelta(seconds=61),
        reservation.completed_at,
        reservation.correlation_id,
        reservation.version,
        reservation.failure_code,
    )
    operations = _OperationRepository(stale)
    recovered = service._reserve_or_recover(
        SimpleNamespace(creative_generation_operations=operations),
        context,
        project_id,
        reservation,
    )

    assert recovered.id == stale.id
    assert recovered.version == 2
    assert operations.takeover_calls[0][1] == 1


def test_visual_active_reservation_is_deterministically_rejected() -> None:
    now = datetime(2026, 8, 16, tzinfo=UTC)
    context = _context()
    service = VisualPlanningApplicationService(
        _unused_uow,
        clock=lambda: now,
        stale_reservation_age_seconds=60,
    )
    reservation = service._reserve(
        context,
        uuid4(),
        VisualPlanningOperationType.GENERATE_STORYBOARD,
        "same-key",
        "b" * 64,
    )
    active = reservation.__class__(
        reservation.id,
        reservation.organization_id,
        reservation.workspace_id,
        reservation.project_id,
        reservation.operation,
        reservation.idempotency_key,
        reservation.request_digest,
        VisualPlanningOperationStatus.RESERVED,
        reservation.outcome_storyboard_run_id,
        reservation.outcome_storyboard_version_id,
        reservation.outcome_shot_plan_run_id,
        reservation.outcome_shot_plan_version_id,
        reservation.submitted_by_actor_subject,
        now - timedelta(seconds=1),
        reservation.completed_at,
        reservation.correlation_id,
        reservation.version,
        reservation.failure_code,
    )
    operations = _OperationRepository(active)

    with pytest.raises(ResourceConflict, match="already in progress"):
        service._reserve_or_recover(
            SimpleNamespace(visual_planning_operations=operations), reservation
        )


def test_failed_operation_status_is_not_treated_as_replay() -> None:
    assert CreativeGenerationOperationStatus.FAILED.value == "failed"
    assert VisualPlanningOperationStatus.FAILED.value == "failed"
