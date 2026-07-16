import hashlib
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.errors import ApplicationError, ResourceConflict, ResourceNotFound
from services.api.app.application.review_revision_delivery_services import (
    ReviewRevisionDeliveryApplicationService,
)
from services.api.app.application.storage import LocalFilesystemStorageAdapter, StorageError
from services.api.app.application.visual_planning_services import (
    ShotPlanGenerationResult,
    StoryboardGenerationResult,
    VisualPlanningApplicationService,
)
from services.api.app.domain import PlanningReviewOutcome, ReviewArtifactType
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_visual_planning_persistence import (
    ProjectSeed,
    ScriptGraph,
    _insert_script_graph,
    _seed_project,
)
from services.api.tests.test_visual_planning_services import _make_script_usable


def _services(
    session_factory: SessionFactory, root: Path
) -> tuple[VisualPlanningApplicationService, ReviewRevisionDeliveryApplicationService]:
    storage = LocalFilesystemStorageAdapter(root)
    return (
        VisualPlanningApplicationService(
            lambda: SqlAlchemyUnitOfWork(session_factory),
        ),
        ReviewRevisionDeliveryApplicationService(
            lambda: SqlAlchemyUnitOfWork(session_factory), storage
        ),
    )


def _prepare_graph(
    session_factory: SessionFactory, engine: Engine, key: str, root: Path
) -> tuple[
    ProjectSeed,
    ScriptGraph,
    StoryboardGenerationResult,
    ShotPlanGenerationResult,
    ReviewRevisionDeliveryApplicationService,
]:
    seed = _seed_project(session_factory, name=f"Stage 13 {key}")
    graph = _insert_script_graph(engine, seed, key)
    _make_script_usable(engine, graph.script_version_id)
    visual, delivery = _services(session_factory, root)
    storyboard = visual.generate_storyboard(
        seed.context, seed.project_id, graph.script_version_id, idempotency_key=f"board-{key}"
    )
    shot_plan = visual.generate_shot_plan(
        seed.context, seed.project_id, storyboard.version.id, idempotency_key=f"shot-{key}"
    )
    return seed, graph, storyboard, shot_plan, delivery


class _FailingFinalizeStorage(LocalFilesystemStorageAdapter):
    def finalize(self, staging_key: str, final_key: str) -> None:
        del staging_key, final_key
        raise StorageError("injected finalize failure")


def test_review_revision_successor_keeps_predecessor_immutable(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
    tmp_path: Path,
) -> None:
    del clean_database
    seed, graph, _storyboard, _shot_plan, delivery = _prepare_graph(
        persistence_session_factory, database_engine, "revision", tmp_path
    )
    review_result = delivery.submit_review(
        seed.context,
        seed.project_id,
        artifact_type=ReviewArtifactType.SCRIPT,
        script_version_id=graph.script_version_id,
        storyboard_version_id=None,
        shot_plan_version_id=None,
        outcome=PlanningReviewOutcome.REVISION_REQUESTED,
        summary="Tighten the opening action.",
        requested_changes={"mode": "valid"},
        idempotency_key="review-revision-1",
    )
    assert review_result.revision_request is not None
    request_id = review_result.revision_request.id
    before = (
        database_engine.connect()
        .execute(
            text(
                "SELECT version_number, content, content_digest, created_at "
                "FROM script_versions WHERE id=:id"
            ),
            {"id": graph.script_version_id},
        )
        .mappings()
        .one()
    )

    completed = delivery.complete_revision(
        seed.context,
        seed.project_id,
        request_id,
        provider_mode="valid",
        idempotency_key="complete-revision-1",
    )
    assert completed.successor_script_version_id is not None
    assert completed.request.status.value == "completed"
    replay = delivery.complete_revision(
        seed.context,
        seed.project_id,
        request_id,
        provider_mode="valid",
        idempotency_key="complete-revision-1",
    )
    assert replay.replayed is True
    assert replay.successor_script_version_id == completed.successor_script_version_id

    with database_engine.connect() as connection:
        after = (
            connection.execute(
                text(
                    "SELECT version_number, content, content_digest, created_at "
                    "FROM script_versions WHERE id=:id"
                ),
                {"id": graph.script_version_id},
            )
            .mappings()
            .one()
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM planning_artifact_revision_links "
                    "WHERE revision_request_id=:id"
                ),
                {"id": request_id},
            )
            == 1
        )
    assert dict(after) == dict(before)


def test_approved_bundle_delivery_and_deterministic_export(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
    tmp_path: Path,
) -> None:
    del clean_database
    seed, graph, storyboard, shot_plan, delivery = _prepare_graph(
        persistence_session_factory, database_engine, "delivery", tmp_path
    )
    review = delivery.submit_review(
        seed.context,
        seed.project_id,
        artifact_type=ReviewArtifactType.PLANNING_BUNDLE,
        script_version_id=graph.script_version_id,
        storyboard_version_id=storyboard.version.id,
        shot_plan_version_id=shot_plan.version.id,
        outcome=PlanningReviewOutcome.APPROVED,
        summary="Approved for handoff.",
        requested_changes={},
        idempotency_key="review-approved-1",
    ).review
    package = delivery.create_delivery_package(
        seed.context,
        seed.project_id,
        script_version_id=graph.script_version_id,
        storyboard_version_id=storyboard.version.id,
        shot_plan_version_id=shot_plan.version.id,
        approval_review_id=review.id,
        idempotency_key="package-1",
    )
    assert package.version.manifest["lineage"]["script_version_id"] == str(graph.script_version_id)  # type: ignore[index]
    first = delivery.export_delivery_package(
        seed.context,
        seed.project_id,
        package.version.id,
        export_format="delivery-package.zip",
        idempotency_key="export-zip-1",
    )
    replay = delivery.export_delivery_package(
        seed.context,
        seed.project_id,
        package.version.id,
        export_format="delivery-package.zip",
        idempotency_key="export-zip-1",
    )
    assert replay.replayed is True
    assert first.file.checksum == replay.file.checksum
    payload = b"".join(delivery.storage.read(first.file.storage_key))
    assert hashlib.sha256(payload).hexdigest() == first.file.checksum


def test_revision_provider_failure_rolls_back_reservation_and_successor(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
    tmp_path: Path,
) -> None:
    del clean_database
    seed, graph, _storyboard, _shot_plan, delivery = _prepare_graph(
        persistence_session_factory, database_engine, "rollback", tmp_path
    )
    request = delivery.submit_review(
        seed.context,
        seed.project_id,
        artifact_type=ReviewArtifactType.SCRIPT,
        script_version_id=graph.script_version_id,
        storyboard_version_id=None,
        shot_plan_version_id=None,
        outcome=PlanningReviewOutcome.REVISION_REQUESTED,
        summary="Try a bounded failure.",
        requested_changes={"mode": "provider_error"},
        idempotency_key="review-rollback-1",
    ).revision_request
    assert request is not None
    with pytest.raises(ApplicationError):
        delivery.complete_revision(
            seed.context,
            seed.project_id,
            request.id,
            provider_mode="provider_error",
            idempotency_key="complete-rollback-1",
        )
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM delivery_operations")) == 1
        assert (
            connection.scalar(text("SELECT count(*) FROM script_versions WHERE version_number > 1"))
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT status FROM planning_revision_requests WHERE id=:id"),
                {"id": request.id},
            )
            == "open"
        )


def test_review_digest_conflict_and_scoped_opaque_lookup(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
    tmp_path: Path,
) -> None:
    del clean_database
    seed, graph, _storyboard, _shot_plan, delivery = _prepare_graph(
        persistence_session_factory, database_engine, "scope", tmp_path
    )
    first = delivery.submit_review(
        seed.context,
        seed.project_id,
        artifact_type=ReviewArtifactType.SCRIPT,
        script_version_id=graph.script_version_id,
        storyboard_version_id=None,
        shot_plan_version_id=None,
        outcome=PlanningReviewOutcome.APPROVED,
        summary="Approved.",
        requested_changes={},
        idempotency_key="review-digest-1",
    )
    replay = delivery.submit_review(
        seed.context,
        seed.project_id,
        artifact_type=ReviewArtifactType.SCRIPT,
        script_version_id=graph.script_version_id,
        storyboard_version_id=None,
        shot_plan_version_id=None,
        outcome=PlanningReviewOutcome.APPROVED,
        summary="Approved.",
        requested_changes={},
        idempotency_key="review-digest-1",
    )
    assert replay.replayed is True
    assert replay.review.id == first.review.id
    with pytest.raises(ResourceConflict):
        delivery.submit_review(
            seed.context,
            seed.project_id,
            artifact_type=ReviewArtifactType.SCRIPT,
            script_version_id=graph.script_version_id,
            storyboard_version_id=None,
            shot_plan_version_id=None,
            outcome=PlanningReviewOutcome.REJECTED,
            summary="Different decision.",
            requested_changes={},
            idempotency_key="review-digest-1",
        )
    other = _prepare_graph(persistence_session_factory, database_engine, "other", tmp_path)[0]
    with pytest.raises(ResourceNotFound):
        delivery.get_review(other.context, other.project_id, first.review.id)


def test_export_storage_failure_compensates_staging_and_rolls_back(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
    tmp_path: Path,
) -> None:
    del clean_database
    seed, graph, storyboard, shot_plan, delivery = _prepare_graph(
        persistence_session_factory, database_engine, "storage-failure", tmp_path
    )
    review = delivery.submit_review(
        seed.context,
        seed.project_id,
        artifact_type=ReviewArtifactType.PLANNING_BUNDLE,
        script_version_id=graph.script_version_id,
        storyboard_version_id=storyboard.version.id,
        shot_plan_version_id=shot_plan.version.id,
        outcome=PlanningReviewOutcome.APPROVED,
        summary="Approved for storage failure test.",
        requested_changes={},
        idempotency_key="storage-review-1",
    ).review
    package = delivery.create_delivery_package(
        seed.context,
        seed.project_id,
        script_version_id=graph.script_version_id,
        storyboard_version_id=storyboard.version.id,
        shot_plan_version_id=shot_plan.version.id,
        approval_review_id=review.id,
        idempotency_key="storage-package-1",
    )
    failing = ReviewRevisionDeliveryApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory),
        _FailingFinalizeStorage(tmp_path),
    )
    with pytest.raises(ApplicationError):
        failing.export_delivery_package(
            seed.context,
            seed.project_id,
            package.version.id,
            export_format="manifest.json",
            idempotency_key="storage-export-1",
        )
    assert list((tmp_path / "staging").iterdir()) == []
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM delivery_export_files")) == 0
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM delivery_operations "
                    "WHERE operation='export_delivery_package'"
                )
            )
            == 0
        )
