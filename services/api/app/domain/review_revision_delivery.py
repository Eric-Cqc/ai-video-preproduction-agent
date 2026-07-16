from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ReviewArtifactType(StrEnum):
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    SHOT_PLAN = "shot_plan"
    PLANNING_BUNDLE = "planning_bundle"


class PlanningReviewOutcome(StrEnum):
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"


class RevisionRequestStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliveryOperationType(StrEnum):
    SUBMIT_PLANNING_REVIEW = "submit_planning_review"
    CREATE_REVISION_REQUEST = "create_revision_request"
    COMPLETE_REVISION_REQUEST = "complete_revision_request"
    CREATE_DELIVERY_PACKAGE = "create_delivery_package"
    EXPORT_DELIVERY_PACKAGE = "export_delivery_package"


class DeliveryOperationStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class PlanningReview:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    artifact_type: ReviewArtifactType
    script_version_id: UUID | None
    storyboard_version_id: UUID | None
    shot_plan_version_id: UUID | None
    review_round: int
    outcome: PlanningReviewOutcome
    summary: str
    requested_changes: dict[str, object]
    reviewed_by_actor_subject: str
    reviewed_at: datetime
    correlation_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlanningRevisionRequest:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    review_id: UUID
    artifact_type: ReviewArtifactType
    source_script_version_id: UUID | None
    source_storyboard_version_id: UUID | None
    source_shot_plan_version_id: UUID | None
    requested_changes: dict[str, object]
    request_digest: str
    status: RevisionRequestStatus
    created_by_actor_subject: str
    created_at: datetime
    completed_at: datetime | None
    successor_script_version_id: UUID | None
    successor_storyboard_version_id: UUID | None
    successor_shot_plan_version_id: UUID | None
    version: int


@dataclass(frozen=True, slots=True)
class ArtifactRevisionLink:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    artifact_type: ReviewArtifactType
    predecessor_version_id: UUID
    successor_version_id: UUID
    predecessor_version_number: int
    successor_version_number: int
    revision_request_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DeliveryPackage:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    current_version_id: UUID | None
    created_by_actor_subject: str
    created_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class DeliveryPackageVersion:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    delivery_package_id: UUID
    version_number: int
    script_version_id: UUID
    storyboard_version_id: UUID
    shot_plan_version_id: UUID
    approval_review_id: UUID
    script_content_digest: str
    storyboard_content_digest: str
    shot_plan_content_digest: str
    manifest_schema_version: str
    manifest: dict[str, object]
    manifest_digest: str
    created_by_actor_subject: str
    created_at: datetime
    supersedes_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class DeliveryExportFile:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    delivery_package_version_id: UUID
    format: str
    filename: str
    storage_adapter: str
    storage_key: str
    checksum: str
    byte_size: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DeliveryOperation:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    operation: DeliveryOperationType
    idempotency_key: str
    request_digest: str
    status: DeliveryOperationStatus
    outcome_review_id: UUID | None
    outcome_revision_request_id: UUID | None
    outcome_delivery_package_id: UUID | None
    outcome_delivery_package_version_id: UUID | None
    outcome_export_file_id: UUID | None
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int
