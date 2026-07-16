from types import TracebackType
from typing import Protocol, Self

from services.api.app.application.repositories import (
    ArtifactRevisionLinkRepository,
    AuditEventRepository,
    BriefCandidateReviewRepository,
    BriefExtractionAttemptRepository,
    BriefExtractionRunRepository,
    BriefIngestionRepository,
    BriefIngestionSourceAssetRepository,
    BriefRepository,
    BriefVersionRepository,
    CreativeConceptCandidateRepository,
    CreativeConceptRunRepository,
    CreativeConceptSelectionRepository,
    CreativeGenerationOperationRepository,
    DeliveryExportFileRepository,
    DeliveryOperationRepository,
    DeliveryPackageRepository,
    DeliveryPackageVersionRepository,
    DocumentExtractionOperationRepository,
    DocumentExtractionRepository,
    MembershipRepository,
    OrganizationRepository,
    PlanningReviewRepository,
    PlanningRevisionRequestRepository,
    ProjectRepository,
    RequirementIssueRepository,
    ScriptRunRepository,
    ScriptVersionRepository,
    ShotPlanRunRepository,
    ShotPlanVersionRepository,
    SourceAssetOperationRepository,
    SourceAssetRepository,
    SourceAssetVersionRepository,
    SourceObjectCleanupRequirementRepository,
    SourceObjectRepository,
    SourceObjectUploadRepository,
    StoryboardRunRepository,
    StoryboardVersionRepository,
    VisualPlanningOperationRepository,
    WorkspaceRepository,
)


class UnitOfWork(Protocol):
    organizations: OrganizationRepository
    workspaces: WorkspaceRepository
    memberships: MembershipRepository
    projects: ProjectRepository
    briefs: BriefRepository
    brief_ingestions: BriefIngestionRepository
    brief_ingestion_source_assets: BriefIngestionSourceAssetRepository
    brief_versions: BriefVersionRepository
    requirement_issues: RequirementIssueRepository
    source_assets: SourceAssetRepository
    source_asset_versions: SourceAssetVersionRepository
    source_asset_operations: SourceAssetOperationRepository
    source_objects: SourceObjectRepository
    source_object_uploads: SourceObjectUploadRepository
    source_object_cleanup_requirements: SourceObjectCleanupRequirementRepository
    document_extractions: DocumentExtractionRepository
    document_extraction_operations: DocumentExtractionOperationRepository
    brief_extraction_runs: BriefExtractionRunRepository
    brief_extraction_attempts: BriefExtractionAttemptRepository
    brief_candidate_reviews: BriefCandidateReviewRepository
    creative_concept_runs: CreativeConceptRunRepository
    creative_concept_candidates: CreativeConceptCandidateRepository
    creative_concept_selections: CreativeConceptSelectionRepository
    script_runs: ScriptRunRepository
    script_versions: ScriptVersionRepository
    creative_generation_operations: CreativeGenerationOperationRepository
    storyboard_runs: StoryboardRunRepository
    storyboard_versions: StoryboardVersionRepository
    shot_plan_runs: ShotPlanRunRepository
    shot_plan_versions: ShotPlanVersionRepository
    visual_planning_operations: VisualPlanningOperationRepository
    audit_events: AuditEventRepository
    planning_reviews: PlanningReviewRepository
    planning_revision_requests: PlanningRevisionRequestRepository
    artifact_revision_links: ArtifactRevisionLinkRepository
    delivery_packages: DeliveryPackageRepository
    delivery_package_versions: DeliveryPackageVersionRepository
    delivery_export_files: DeliveryExportFileRepository
    delivery_operations: DeliveryOperationRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
