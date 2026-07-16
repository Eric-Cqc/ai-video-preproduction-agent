from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.api.app.application.errors import ResourceConflict
from services.api.app.domain import (
    ArtifactRevisionLink,
    DeliveryExportFile,
    DeliveryOperation,
    DeliveryOperationStatus,
    DeliveryOperationType,
    DeliveryPackage,
    DeliveryPackageVersion,
    PlanningReview,
    PlanningReviewOutcome,
    PlanningRevisionRequest,
    ReviewArtifactType,
    RevisionRequestStatus,
    VersionConflict,
)
from services.api.app.infrastructure.models import (
    DeliveryExportFileRecord,
    DeliveryOperationRecord,
    DeliveryPackageRecord,
    DeliveryPackageVersionRecord,
    PlanningArtifactRevisionLinkRecord,
    PlanningReviewRecord,
    PlanningRevisionRequestRecord,
)


def _flush(session: Session, record: object) -> None:
    session.add(record)
    try:
        session.flush()
    except Exception as error:
        raise ResourceConflict("review or delivery record could not be persisted") from error


def _to_review(row: PlanningReviewRecord) -> PlanningReview:
    return PlanningReview(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        artifact_type=ReviewArtifactType(row.artifact_type),
        script_version_id=row.script_version_id,
        storyboard_version_id=row.storyboard_version_id,
        shot_plan_version_id=row.shot_plan_version_id,
        review_round=row.review_round,
        outcome=PlanningReviewOutcome(row.outcome),
        summary=row.summary,
        requested_changes=dict(row.requested_changes),
        reviewed_by_actor_subject=row.reviewed_by_actor_subject,
        reviewed_at=row.reviewed_at,
        correlation_id=row.correlation_id,
        created_at=row.created_at,
    )


def _to_revision(row: PlanningRevisionRequestRecord) -> PlanningRevisionRequest:
    return PlanningRevisionRequest(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        review_id=row.review_id,
        artifact_type=ReviewArtifactType(row.artifact_type),
        source_script_version_id=row.source_script_version_id,
        source_storyboard_version_id=row.source_storyboard_version_id,
        source_shot_plan_version_id=row.source_shot_plan_version_id,
        requested_changes=dict(row.requested_changes),
        request_digest=row.request_digest,
        status=RevisionRequestStatus(row.status),
        created_by_actor_subject=row.created_by_actor_subject,
        created_at=row.created_at,
        completed_at=row.completed_at,
        successor_script_version_id=row.successor_script_version_id,
        successor_storyboard_version_id=row.successor_storyboard_version_id,
        successor_shot_plan_version_id=row.successor_shot_plan_version_id,
        version=row.version,
    )


def _to_link(row: PlanningArtifactRevisionLinkRecord) -> ArtifactRevisionLink:
    return ArtifactRevisionLink(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        artifact_type=ReviewArtifactType(row.artifact_type),
        predecessor_version_id=row.predecessor_version_id,
        successor_version_id=row.successor_version_id,
        predecessor_version_number=row.predecessor_version_number,
        successor_version_number=row.successor_version_number,
        revision_request_id=row.revision_request_id,
        created_at=row.created_at,
    )


def _to_package(row: DeliveryPackageRecord) -> DeliveryPackage:
    return DeliveryPackage(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        current_version_id=row.current_version_id,
        created_by_actor_subject=row.created_by_actor_subject,
        created_at=row.created_at,
        version=row.version,
    )


def _to_package_version(row: DeliveryPackageVersionRecord) -> DeliveryPackageVersion:
    return DeliveryPackageVersion(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        delivery_package_id=row.delivery_package_id,
        version_number=row.version_number,
        script_version_id=row.script_version_id,
        storyboard_version_id=row.storyboard_version_id,
        shot_plan_version_id=row.shot_plan_version_id,
        approval_review_id=row.approval_review_id,
        script_content_digest=row.script_content_digest,
        storyboard_content_digest=row.storyboard_content_digest,
        shot_plan_content_digest=row.shot_plan_content_digest,
        manifest_schema_version=row.manifest_schema_version,
        manifest=dict(row.manifest),
        manifest_digest=row.manifest_digest,
        created_by_actor_subject=row.created_by_actor_subject,
        created_at=row.created_at,
        supersedes_version_id=row.supersedes_version_id,
    )


def _to_export(row: DeliveryExportFileRecord) -> DeliveryExportFile:
    return DeliveryExportFile(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        delivery_package_version_id=row.delivery_package_version_id,
        format=row.format,
        filename=row.filename,
        storage_adapter=row.storage_adapter,
        storage_key=row.storage_key,
        checksum=row.checksum,
        byte_size=row.byte_size,
        created_at=row.created_at,
    )


def _to_operation(row: DeliveryOperationRecord) -> DeliveryOperation:
    return DeliveryOperation(
        id=row.id,
        organization_id=row.organization_id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        operation=DeliveryOperationType(row.operation),
        idempotency_key=row.idempotency_key,
        request_digest=row.request_digest,
        status=DeliveryOperationStatus(row.status),
        outcome_review_id=row.outcome_review_id,
        outcome_revision_request_id=row.outcome_revision_request_id,
        outcome_delivery_package_id=row.outcome_delivery_package_id,
        outcome_delivery_package_version_id=row.outcome_delivery_package_version_id,
        outcome_export_file_id=row.outcome_export_file_id,
        submitted_by_actor_subject=row.submitted_by_actor_subject,
        submitted_at=row.submitted_at,
        completed_at=row.completed_at,
        correlation_id=row.correlation_id,
        version=row.version,
    )


class SqlAlchemyPlanningReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: PlanningReview) -> PlanningReview:
        _flush(self.session, PlanningReviewRecord(**_review_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, review_id: UUID
    ) -> PlanningReview | None:
        row = self.session.scalar(
            select(PlanningReviewRecord).where(
                PlanningReviewRecord.organization_id == organization_id,
                PlanningReviewRecord.workspace_id == workspace_id,
                PlanningReviewRecord.project_id == project_id,
                PlanningReviewRecord.id == review_id,
            )
        )
        return _to_review(row) if row is not None else None

    def list(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[PlanningReview]:
        rows = self.session.scalars(
            select(PlanningReviewRecord)
            .where(
                PlanningReviewRecord.organization_id == organization_id,
                PlanningReviewRecord.workspace_id == workspace_id,
                PlanningReviewRecord.project_id == project_id,
            )
            .order_by(PlanningReviewRecord.created_at, PlanningReviewRecord.review_round)
        ).all()
        return [_to_review(row) for row in rows]

    def next_round(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        artifact_type: ReviewArtifactType,
        script_version_id: UUID | None,
        storyboard_version_id: UUID | None,
        shot_plan_version_id: UUID | None,
    ) -> int:
        predicates = [
            PlanningReviewRecord.organization_id == organization_id,
            PlanningReviewRecord.workspace_id == workspace_id,
            PlanningReviewRecord.project_id == project_id,
            PlanningReviewRecord.artifact_type == artifact_type.value,
        ]
        predicates.extend(
            column == identifier if identifier is not None else column.is_(None)
            for column, identifier in (
                (PlanningReviewRecord.script_version_id, script_version_id),
                (PlanningReviewRecord.storyboard_version_id, storyboard_version_id),
                (PlanningReviewRecord.shot_plan_version_id, shot_plan_version_id),
            )
        )
        value = self.session.scalar(
            select(func.coalesce(func.max(PlanningReviewRecord.review_round), 0)).where(*predicates)
        )
        return int(value or 0) + 1


class SqlAlchemyPlanningRevisionRequestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: PlanningRevisionRequest) -> PlanningRevisionRequest:
        _flush(self.session, PlanningRevisionRequestRecord(**_revision_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, request_id: UUID
    ) -> PlanningRevisionRequest | None:
        row = self.session.scalar(
            select(PlanningRevisionRequestRecord).where(
                PlanningRevisionRequestRecord.organization_id == organization_id,
                PlanningRevisionRequestRecord.workspace_id == workspace_id,
                PlanningRevisionRequestRecord.project_id == project_id,
                PlanningRevisionRequestRecord.id == request_id,
            )
        )
        return _to_revision(row) if row is not None else None

    def update_completed(
        self, value: PlanningRevisionRequest, *, expected_version: int
    ) -> PlanningRevisionRequest:
        row = self.session.scalar(
            update(PlanningRevisionRequestRecord)
            .where(
                PlanningRevisionRequestRecord.id == value.id,
                PlanningRevisionRequestRecord.organization_id == value.organization_id,
                PlanningRevisionRequestRecord.workspace_id == value.workspace_id,
                PlanningRevisionRequestRecord.project_id == value.project_id,
                PlanningRevisionRequestRecord.status == RevisionRequestStatus.OPEN.value,
                PlanningRevisionRequestRecord.version == expected_version,
            )
            .values(**_revision_values(value))
            .returning(PlanningRevisionRequestRecord)
        )
        if row is None:
            raise VersionConflict("revision request changed before completion")
        return _to_revision(row)

    def update_cancelled(
        self, value: PlanningRevisionRequest, *, expected_version: int
    ) -> PlanningRevisionRequest:
        row = self.session.scalar(
            update(PlanningRevisionRequestRecord)
            .where(
                PlanningRevisionRequestRecord.id == value.id,
                PlanningRevisionRequestRecord.organization_id == value.organization_id,
                PlanningRevisionRequestRecord.workspace_id == value.workspace_id,
                PlanningRevisionRequestRecord.project_id == value.project_id,
                PlanningRevisionRequestRecord.status == RevisionRequestStatus.OPEN.value,
                PlanningRevisionRequestRecord.version == expected_version,
            )
            .values(status=RevisionRequestStatus.CANCELLED.value, version=value.version)
            .returning(PlanningRevisionRequestRecord)
        )
        if row is None:
            raise VersionConflict("revision request changed before cancellation")
        return _to_revision(row)


class SqlAlchemyArtifactRevisionLinkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: ArtifactRevisionLink) -> ArtifactRevisionLink:
        _flush(self.session, PlanningArtifactRevisionLinkRecord(**_link_values(value)))
        return value

    def get_for_predecessor(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, predecessor_id: UUID
    ) -> ArtifactRevisionLink | None:
        row = self.session.scalar(
            select(PlanningArtifactRevisionLinkRecord).where(
                PlanningArtifactRevisionLinkRecord.organization_id == organization_id,
                PlanningArtifactRevisionLinkRecord.workspace_id == workspace_id,
                PlanningArtifactRevisionLinkRecord.project_id == project_id,
                PlanningArtifactRevisionLinkRecord.predecessor_version_id == predecessor_id,
            )
        )
        return _to_link(row) if row is not None else None


class SqlAlchemyDeliveryPackageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: DeliveryPackage) -> DeliveryPackage:
        _flush(self.session, DeliveryPackageRecord(**_package_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, package_id: UUID
    ) -> DeliveryPackage | None:
        row = self.session.scalar(
            select(DeliveryPackageRecord).where(
                DeliveryPackageRecord.organization_id == organization_id,
                DeliveryPackageRecord.workspace_id == workspace_id,
                DeliveryPackageRecord.project_id == project_id,
                DeliveryPackageRecord.id == package_id,
            )
        )
        return _to_package(row) if row is not None else None

    def update_current(self, value: DeliveryPackage, *, expected_version: int) -> DeliveryPackage:
        row = self.session.scalar(
            update(DeliveryPackageRecord)
            .where(
                DeliveryPackageRecord.id == value.id,
                DeliveryPackageRecord.organization_id == value.organization_id,
                DeliveryPackageRecord.workspace_id == value.workspace_id,
                DeliveryPackageRecord.project_id == value.project_id,
                DeliveryPackageRecord.version == expected_version,
            )
            .values(**_package_values(value))
            .returning(DeliveryPackageRecord)
        )
        if row is None:
            raise VersionConflict("delivery package changed before pointer update")
        return _to_package(row)


class SqlAlchemyDeliveryPackageVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: DeliveryPackageVersion) -> DeliveryPackageVersion:
        _flush(self.session, DeliveryPackageVersionRecord(**_package_version_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, version_id: UUID
    ) -> DeliveryPackageVersion | None:
        row = self.session.scalar(
            select(DeliveryPackageVersionRecord).where(
                DeliveryPackageVersionRecord.organization_id == organization_id,
                DeliveryPackageVersionRecord.workspace_id == workspace_id,
                DeliveryPackageVersionRecord.project_id == project_id,
                DeliveryPackageVersionRecord.id == version_id,
            )
        )
        return _to_package_version(row) if row is not None else None


class SqlAlchemyDeliveryExportFileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, value: DeliveryExportFile) -> DeliveryExportFile:
        _flush(self.session, DeliveryExportFileRecord(**_export_values(value)))
        return value

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, export_id: UUID
    ) -> DeliveryExportFile | None:
        row = self.session.scalar(
            select(DeliveryExportFileRecord).where(
                DeliveryExportFileRecord.organization_id == organization_id,
                DeliveryExportFileRecord.workspace_id == workspace_id,
                DeliveryExportFileRecord.project_id == project_id,
                DeliveryExportFileRecord.id == export_id,
            )
        )
        return _to_export(row) if row is not None else None

    def list_for_package_version(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, package_version_id: UUID
    ) -> list[DeliveryExportFile]:
        rows = self.session.scalars(
            select(DeliveryExportFileRecord)
            .where(
                DeliveryExportFileRecord.organization_id == organization_id,
                DeliveryExportFileRecord.workspace_id == workspace_id,
                DeliveryExportFileRecord.project_id == project_id,
                DeliveryExportFileRecord.delivery_package_version_id == package_version_id,
            )
            .order_by(DeliveryExportFileRecord.format)
        ).all()
        return [_to_export(row) for row in rows]


class SqlAlchemyDeliveryOperationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(self, value: DeliveryOperation) -> DeliveryOperation | None:
        row = self.session.scalar(
            insert(DeliveryOperationRecord)
            .values(**_operation_values(value))
            .on_conflict_do_nothing()
            .returning(DeliveryOperationRecord)
        )
        return _to_operation(row) if row is not None else None

    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: DeliveryOperationType,
        idempotency_key: str,
    ) -> DeliveryOperation | None:
        row = self.session.scalar(
            select(DeliveryOperationRecord).where(
                DeliveryOperationRecord.organization_id == organization_id,
                DeliveryOperationRecord.workspace_id == workspace_id,
                DeliveryOperationRecord.project_id == project_id,
                DeliveryOperationRecord.operation == operation.value,
                DeliveryOperationRecord.idempotency_key == idempotency_key,
            )
        )
        return _to_operation(row) if row is not None else None

    def finalize_accepted(
        self, value: DeliveryOperation, *, expected_version: int
    ) -> DeliveryOperation:
        row = self.session.scalar(
            update(DeliveryOperationRecord)
            .where(
                DeliveryOperationRecord.id == value.id,
                DeliveryOperationRecord.organization_id == value.organization_id,
                DeliveryOperationRecord.workspace_id == value.workspace_id,
                DeliveryOperationRecord.project_id == value.project_id,
                DeliveryOperationRecord.operation == value.operation.value,
                DeliveryOperationRecord.idempotency_key == value.idempotency_key,
                DeliveryOperationRecord.request_digest == value.request_digest,
                DeliveryOperationRecord.status == DeliveryOperationStatus.RESERVED.value,
                DeliveryOperationRecord.version == expected_version,
            )
            .values(**_operation_values(value))
            .returning(DeliveryOperationRecord)
        )
        if row is None:
            raise VersionConflict("delivery operation changed before finalization")
        return _to_operation(row)


def _review_values(value: PlanningReview) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "artifact_type": value.artifact_type.value,
        "script_version_id": value.script_version_id,
        "storyboard_version_id": value.storyboard_version_id,
        "shot_plan_version_id": value.shot_plan_version_id,
        "review_round": value.review_round,
        "outcome": value.outcome.value,
        "summary": value.summary,
        "requested_changes": value.requested_changes,
        "reviewed_by_actor_subject": value.reviewed_by_actor_subject,
        "reviewed_at": value.reviewed_at,
        "correlation_id": value.correlation_id,
        "created_at": value.created_at,
    }


def _revision_values(value: PlanningRevisionRequest) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "review_id": value.review_id,
        "artifact_type": value.artifact_type.value,
        "source_script_version_id": value.source_script_version_id,
        "source_storyboard_version_id": value.source_storyboard_version_id,
        "source_shot_plan_version_id": value.source_shot_plan_version_id,
        "requested_changes": value.requested_changes,
        "request_digest": value.request_digest,
        "status": value.status.value,
        "created_by_actor_subject": value.created_by_actor_subject,
        "created_at": value.created_at,
        "completed_at": value.completed_at,
        "successor_script_version_id": value.successor_script_version_id,
        "successor_storyboard_version_id": value.successor_storyboard_version_id,
        "successor_shot_plan_version_id": value.successor_shot_plan_version_id,
        "version": value.version,
    }


def _link_values(value: ArtifactRevisionLink) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "artifact_type": value.artifact_type.value,
        "predecessor_version_id": value.predecessor_version_id,
        "successor_version_id": value.successor_version_id,
        "predecessor_version_number": value.predecessor_version_number,
        "successor_version_number": value.successor_version_number,
        "revision_request_id": value.revision_request_id,
        "created_at": value.created_at,
    }


def _package_values(value: DeliveryPackage) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "current_version_id": value.current_version_id,
        "created_by_actor_subject": value.created_by_actor_subject,
        "created_at": value.created_at,
        "version": value.version,
    }


def _package_version_values(value: DeliveryPackageVersion) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "delivery_package_id": value.delivery_package_id,
        "version_number": value.version_number,
        "script_version_id": value.script_version_id,
        "storyboard_version_id": value.storyboard_version_id,
        "shot_plan_version_id": value.shot_plan_version_id,
        "approval_review_id": value.approval_review_id,
        "script_content_digest": value.script_content_digest,
        "storyboard_content_digest": value.storyboard_content_digest,
        "shot_plan_content_digest": value.shot_plan_content_digest,
        "manifest_schema_version": value.manifest_schema_version,
        "manifest": value.manifest,
        "manifest_digest": value.manifest_digest,
        "created_by_actor_subject": value.created_by_actor_subject,
        "created_at": value.created_at,
        "supersedes_version_id": value.supersedes_version_id,
    }


def _export_values(value: DeliveryExportFile) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "delivery_package_version_id": value.delivery_package_version_id,
        "format": value.format,
        "filename": value.filename,
        "storage_adapter": value.storage_adapter,
        "storage_key": value.storage_key,
        "checksum": value.checksum,
        "byte_size": value.byte_size,
        "created_at": value.created_at,
    }


def _operation_values(value: DeliveryOperation) -> dict[str, object]:
    return {
        "id": value.id,
        "organization_id": value.organization_id,
        "workspace_id": value.workspace_id,
        "project_id": value.project_id,
        "operation": value.operation.value,
        "idempotency_key": value.idempotency_key,
        "request_digest": value.request_digest,
        "status": value.status.value,
        "outcome_review_id": value.outcome_review_id,
        "outcome_revision_request_id": value.outcome_revision_request_id,
        "outcome_delivery_package_id": value.outcome_delivery_package_id,
        "outcome_delivery_package_version_id": value.outcome_delivery_package_version_id,
        "outcome_export_file_id": value.outcome_export_file_id,
        "submitted_by_actor_subject": value.submitted_by_actor_subject,
        "submitted_at": value.submitted_at,
        "completed_at": value.completed_at,
        "correlation_id": value.correlation_id,
        "version": value.version,
    }
