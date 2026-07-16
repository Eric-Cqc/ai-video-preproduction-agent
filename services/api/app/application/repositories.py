from datetime import datetime
from typing import Protocol
from uuid import UUID

from services.api.app.domain import (
    ArtifactRevisionLink,
    AuditEvent,
    Brief,
    BriefCandidateReview,
    BriefExtractionAttempt,
    BriefExtractionRun,
    BriefIngestion,
    BriefIngestionOperation,
    BriefIngestionSourceAsset,
    BriefVersion,
    CreativeConceptCandidate,
    CreativeConceptRun,
    CreativeConceptSelection,
    CreativeGenerationOperation,
    CreativeGenerationOperationType,
    DeliveryExportFile,
    DeliveryOperation,
    DeliveryOperationType,
    DeliveryPackage,
    DeliveryPackageVersion,
    DocumentExtraction,
    DocumentExtractionOperation,
    Membership,
    Organization,
    PlanningReview,
    PlanningRevisionRequest,
    Project,
    RequirementIssue,
    RequirementIssueStatus,
    ReviewArtifactType,
    ScriptRun,
    ScriptVersion,
    ShotPlanRun,
    ShotPlanVersion,
    SourceAsset,
    SourceAssetOperation,
    SourceAssetOperationType,
    SourceAssetVersion,
    SourceObject,
    SourceObjectCleanupRequirement,
    SourceObjectUpload,
    StoryboardRun,
    StoryboardVersion,
    VisualPlanningOperation,
    VisualPlanningOperationType,
    Workspace,
)


class OrganizationRepository(Protocol):
    def add(self, organization: Organization) -> Organization: ...

    def get(self, organization_id: UUID) -> Organization | None: ...


class WorkspaceRepository(Protocol):
    def add(self, workspace: Workspace) -> Workspace: ...

    def get(self, organization_id: UUID, workspace_id: UUID) -> Workspace | None: ...


class MembershipRepository(Protocol):
    def add(self, membership: Membership) -> Membership: ...

    def find_any_for_organization(
        self, organization_id: UUID, actor_subject: str
    ) -> Membership | None: ...

    def find_effective(
        self, organization_id: UUID, workspace_id: UUID, actor_subject: str
    ) -> Membership | None: ...

    def find_organization_wide(
        self, organization_id: UUID, actor_subject: str
    ) -> Membership | None: ...


class ProjectRepository(Protocol):
    def add(self, project: Project) -> Project: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> Project | None: ...

    def list(self, organization_id: UUID, workspace_id: UUID) -> list[Project]: ...

    def update(self, project: Project, *, expected_version: int) -> Project: ...


class BriefRepository(Protocol):
    def add(self, brief: Brief) -> Brief: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> Brief | None: ...

    def list(self, organization_id: UUID, workspace_id: UUID, project_id: UUID) -> list[Brief]: ...

    def update(
        self,
        brief: Brief,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> Brief: ...


class BriefIngestionRepository(Protocol):
    def reserve(self, ingestion: BriefIngestion) -> BriefIngestion | None: ...

    def finalize_accepted(
        self,
        ingestion: BriefIngestion,
        *,
        brief_id: UUID,
        brief_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> BriefIngestion: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, ingestion_id: UUID
    ) -> BriefIngestion | None: ...

    def get_by_idempotency_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: BriefIngestionOperation,
        idempotency_key: str,
    ) -> BriefIngestion | None: ...


class BriefIngestionSourceAssetRepository(Protocol):
    def add_for_accepted_ingestion(
        self, attachment: BriefIngestionSourceAsset
    ) -> BriefIngestionSourceAsset: ...

    def list_for_ingestion(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_ingestion_id: UUID
    ) -> list[BriefIngestionSourceAsset]: ...


class BriefVersionRepository(Protocol):
    def add(self, version: BriefVersion) -> BriefVersion: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> BriefVersion | None: ...

    def list(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> list[BriefVersion]: ...

    def submit_for_review(self, version: BriefVersion) -> BriefVersion: ...

    def approve(self, version: BriefVersion) -> BriefVersion: ...

    def supersede(self, version: BriefVersion) -> BriefVersion: ...


class SourceAssetRepository(Protocol):
    def add(self, asset: SourceAsset) -> SourceAsset: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> SourceAsset | None: ...

    def list(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[SourceAsset]: ...

    def compare_and_move_pointer(
        self,
        asset: SourceAsset,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAsset: ...

    def compare_and_archive(
        self,
        asset: SourceAsset,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAsset: ...


class SourceAssetVersionRepository(Protocol):
    def add(self, version: SourceAssetVersion) -> SourceAssetVersion: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        version_id: UUID,
    ) -> SourceAssetVersion | None: ...

    def list_for_asset(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> list[SourceAssetVersion]: ...

    def find_declared_duplicate_within_project(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        *,
        checksum_algorithm: str,
        checksum_value: str,
        byte_size: int,
        media_type: str,
        exclude_source_asset_id: UUID | None = None,
    ) -> int: ...


class SourceAssetOperationRepository(Protocol):
    def reserve(self, operation: SourceAssetOperation) -> SourceAssetOperation | None: ...

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: SourceAssetOperationType,
        idempotency_key: str,
    ) -> SourceAssetOperation | None: ...

    def finalize_accepted(
        self,
        operation: SourceAssetOperation,
        *,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> SourceAssetOperation: ...


class SourceObjectRepository(Protocol):
    def add(self, source_object: SourceObject) -> SourceObject: ...

    def get_for_version(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
    ) -> SourceObject | None: ...


class SourceObjectUploadRepository(Protocol):
    def reserve(self, upload: SourceObjectUpload) -> SourceObjectUpload | None: ...

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> SourceObjectUpload | None: ...

    def finalize_accepted(
        self,
        upload: SourceObjectUpload,
        *,
        source_object_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> SourceObjectUpload: ...


class SourceObjectCleanupRequirementRepository(Protocol):
    def add(
        self, requirement: SourceObjectCleanupRequirement
    ) -> SourceObjectCleanupRequirement: ...


class DocumentExtractionRepository(Protocol):
    def add(self, extraction: DocumentExtraction) -> DocumentExtraction: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        extraction_id: UUID,
    ) -> DocumentExtraction | None: ...


class DocumentExtractionOperationRepository(Protocol):
    def reserve(
        self, operation: DocumentExtractionOperation
    ) -> DocumentExtractionOperation | None: ...

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        idempotency_key: str,
    ) -> DocumentExtractionOperation | None: ...

    def finalize_accepted(
        self,
        operation: DocumentExtractionOperation,
        *,
        extraction_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> DocumentExtractionOperation: ...


class BriefExtractionRunRepository(Protocol):
    def add(self, run: BriefExtractionRun) -> BriefExtractionRun: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        run_id: UUID,
    ) -> BriefExtractionRun | None: ...


class BriefExtractionAttemptRepository(Protocol):
    def add(self, attempt: BriefExtractionAttempt) -> BriefExtractionAttempt: ...

    def list_for_run(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        run_id: UUID,
    ) -> list[BriefExtractionAttempt]: ...


class BriefCandidateReviewRepository(Protocol):
    def reserve(self, review: BriefCandidateReview) -> BriefCandidateReview | None: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, review_id: UUID
    ) -> BriefCandidateReview | None: ...

    def get_for_run(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> BriefCandidateReview | None: ...

    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        action: str,
        idempotency_key: str,
    ) -> BriefCandidateReview | None: ...

    def finalize(
        self, review: BriefCandidateReview, *, expected_version: int
    ) -> BriefCandidateReview: ...


class CreativeConceptRunRepository(Protocol):
    def add(self, run: CreativeConceptRun) -> CreativeConceptRun: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> CreativeConceptRun | None: ...


class CreativeConceptCandidateRepository(Protocol):
    def add(self, candidate: CreativeConceptCandidate) -> CreativeConceptCandidate: ...
    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        run_id: UUID,
        candidate_id: UUID,
    ) -> CreativeConceptCandidate | None: ...
    def list_for_run(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> list[CreativeConceptCandidate]: ...


class CreativeConceptSelectionRepository(Protocol):
    def add(self, selection: CreativeConceptSelection) -> CreativeConceptSelection: ...
    def get_for_run(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> CreativeConceptSelection | None: ...


class ScriptRunRepository(Protocol):
    def add(self, run: ScriptRun) -> ScriptRun: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, run_id: UUID
    ) -> ScriptRun | None: ...


class ScriptVersionRepository(Protocol):
    def add(self, version: ScriptVersion) -> ScriptVersion: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, version_id: UUID
    ) -> ScriptVersion | None: ...


class CreativeGenerationOperationRepository(Protocol):
    def reserve(
        self, operation: CreativeGenerationOperation
    ) -> CreativeGenerationOperation | None: ...
    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: CreativeGenerationOperationType,
        idempotency_key: str,
    ) -> CreativeGenerationOperation | None: ...
    def finalize_accepted(
        self, operation: CreativeGenerationOperation, *, expected_version: int
    ) -> CreativeGenerationOperation: ...


class StoryboardRunRepository(Protocol):
    def add(self, value: StoryboardRun) -> StoryboardRun: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> StoryboardRun | None: ...


class StoryboardVersionRepository(Protocol):
    def add(self, value: StoryboardVersion) -> StoryboardVersion: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> StoryboardVersion | None: ...
    def get_for_run(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        storyboard_run_id: UUID,
        version_number: int,
    ) -> StoryboardVersion | None: ...


class ShotPlanRunRepository(Protocol):
    def add(self, value: ShotPlanRun) -> ShotPlanRun: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> ShotPlanRun | None: ...


class ShotPlanVersionRepository(Protocol):
    def add(self, value: ShotPlanVersion) -> ShotPlanVersion: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, value_id: UUID
    ) -> ShotPlanVersion | None: ...
    def get_for_run(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        shot_plan_run_id: UUID,
        version_number: int,
    ) -> ShotPlanVersion | None: ...


class VisualPlanningOperationRepository(Protocol):
    def reserve(self, value: VisualPlanningOperation) -> VisualPlanningOperation | None: ...
    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: VisualPlanningOperationType,
        idempotency_key: str,
    ) -> VisualPlanningOperation | None: ...
    def finalize_accepted(
        self, value: VisualPlanningOperation, *, expected_version: int
    ) -> VisualPlanningOperation: ...


class PlanningReviewRepository(Protocol):
    def add(self, value: PlanningReview) -> PlanningReview: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, review_id: UUID
    ) -> PlanningReview | None: ...
    def list(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[PlanningReview]: ...
    def next_round(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        artifact_type: ReviewArtifactType,
        script_version_id: UUID | None,
        storyboard_version_id: UUID | None,
        shot_plan_version_id: UUID | None,
    ) -> int: ...


class PlanningRevisionRequestRepository(Protocol):
    def add(self, value: PlanningRevisionRequest) -> PlanningRevisionRequest: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, request_id: UUID
    ) -> PlanningRevisionRequest | None: ...
    def update_completed(
        self, value: PlanningRevisionRequest, *, expected_version: int
    ) -> PlanningRevisionRequest: ...
    def update_cancelled(
        self, value: PlanningRevisionRequest, *, expected_version: int
    ) -> PlanningRevisionRequest: ...


class ArtifactRevisionLinkRepository(Protocol):
    def add(self, value: ArtifactRevisionLink) -> ArtifactRevisionLink: ...
    def get_for_predecessor(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, predecessor_id: UUID
    ) -> ArtifactRevisionLink | None: ...


class DeliveryPackageRepository(Protocol):
    def add(self, value: DeliveryPackage) -> DeliveryPackage: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, package_id: UUID
    ) -> DeliveryPackage | None: ...
    def update_current(
        self, value: DeliveryPackage, *, expected_version: int
    ) -> DeliveryPackage: ...


class DeliveryPackageVersionRepository(Protocol):
    def add(self, value: DeliveryPackageVersion) -> DeliveryPackageVersion: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, version_id: UUID
    ) -> DeliveryPackageVersion | None: ...


class DeliveryExportFileRepository(Protocol):
    def add(self, value: DeliveryExportFile) -> DeliveryExportFile: ...
    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, export_id: UUID
    ) -> DeliveryExportFile | None: ...
    def list_for_package_version(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        package_version_id: UUID,
    ) -> list[DeliveryExportFile]: ...


class DeliveryOperationRepository(Protocol):
    def reserve(self, value: DeliveryOperation) -> DeliveryOperation | None: ...
    def get_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: DeliveryOperationType,
        idempotency_key: str,
    ) -> DeliveryOperation | None: ...
    def finalize_accepted(
        self, value: DeliveryOperation, *, expected_version: int
    ) -> DeliveryOperation: ...


class RequirementIssueRepository(Protocol):
    def add(self, issue: RequirementIssue) -> RequirementIssue: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        issue_id: UUID,
    ) -> RequirementIssue | None: ...

    def list(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> list[RequirementIssue]: ...

    def count_open_blocking(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> int: ...

    def update(
        self,
        issue: RequirementIssue,
        *,
        expected_version: int,
        expected_status: RequirementIssueStatus,
    ) -> RequirementIssue: ...


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...

    def list_for_project(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[AuditEvent]: ...

    def list_for_brief(
        self, organization_id: UUID, workspace_id: UUID, brief_id: UUID
    ) -> list[AuditEvent]: ...
