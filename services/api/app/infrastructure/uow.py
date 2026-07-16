from types import TracebackType

from sqlalchemy.orm import Session

from services.api.app.application.repositories import (
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
    DocumentExtractionOperationRepository,
    DocumentExtractionRepository,
    MembershipRepository,
    OrganizationRepository,
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
from services.api.app.infrastructure.creative_repositories import (
    SqlAlchemyCreativeConceptCandidateRepository,
    SqlAlchemyCreativeConceptRunRepository,
    SqlAlchemyCreativeConceptSelectionRepository,
    SqlAlchemyCreativeGenerationOperationRepository,
    SqlAlchemyScriptRunRepository,
    SqlAlchemyScriptVersionRepository,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyBriefCandidateReviewRepository,
    SqlAlchemyBriefExtractionAttemptRepository,
    SqlAlchemyBriefExtractionRunRepository,
    SqlAlchemyBriefIngestionRepository,
    SqlAlchemyBriefIngestionSourceAssetRepository,
    SqlAlchemyBriefRepository,
    SqlAlchemyBriefVersionRepository,
    SqlAlchemyDocumentExtractionOperationRepository,
    SqlAlchemyDocumentExtractionRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyRequirementIssueRepository,
    SqlAlchemySourceAssetOperationRepository,
    SqlAlchemySourceAssetRepository,
    SqlAlchemySourceAssetVersionRepository,
    SqlAlchemySourceObjectCleanupRequirementRepository,
    SqlAlchemySourceObjectRepository,
    SqlAlchemySourceObjectUploadRepository,
    SqlAlchemyWorkspaceRepository,
)
from services.api.app.infrastructure.visual_planning_repositories import (
    SqlAlchemyShotPlanRunRepository,
    SqlAlchemyShotPlanVersionRepository,
    SqlAlchemyStoryboardRunRepository,
    SqlAlchemyStoryboardVersionRepository,
    SqlAlchemyVisualPlanningOperationRepository,
)


class SqlAlchemyUnitOfWork:
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

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self.session_factory()
        self.organizations = SqlAlchemyOrganizationRepository(self.session)
        self.workspaces = SqlAlchemyWorkspaceRepository(self.session)
        self.memberships = SqlAlchemyMembershipRepository(self.session)
        self.projects = SqlAlchemyProjectRepository(self.session)
        self.briefs = SqlAlchemyBriefRepository(self.session)
        self.brief_ingestions = SqlAlchemyBriefIngestionRepository(self.session)
        self.brief_ingestion_source_assets = SqlAlchemyBriefIngestionSourceAssetRepository(
            self.session
        )
        self.brief_versions = SqlAlchemyBriefVersionRepository(self.session)
        self.requirement_issues = SqlAlchemyRequirementIssueRepository(self.session)
        self.source_assets = SqlAlchemySourceAssetRepository(self.session)
        self.source_asset_versions = SqlAlchemySourceAssetVersionRepository(self.session)
        self.source_asset_operations = SqlAlchemySourceAssetOperationRepository(self.session)
        self.source_objects = SqlAlchemySourceObjectRepository(self.session)
        self.source_object_uploads = SqlAlchemySourceObjectUploadRepository(self.session)
        self.source_object_cleanup_requirements = (
            SqlAlchemySourceObjectCleanupRequirementRepository(self.session)
        )
        self.document_extractions = SqlAlchemyDocumentExtractionRepository(self.session)
        self.document_extraction_operations = SqlAlchemyDocumentExtractionOperationRepository(
            self.session
        )
        self.brief_extraction_runs = SqlAlchemyBriefExtractionRunRepository(self.session)
        self.brief_extraction_attempts = SqlAlchemyBriefExtractionAttemptRepository(self.session)
        self.brief_candidate_reviews = SqlAlchemyBriefCandidateReviewRepository(self.session)
        self.creative_concept_runs = SqlAlchemyCreativeConceptRunRepository(self.session)
        self.creative_concept_candidates = SqlAlchemyCreativeConceptCandidateRepository(
            self.session
        )
        self.creative_concept_selections = SqlAlchemyCreativeConceptSelectionRepository(
            self.session
        )
        self.script_runs = SqlAlchemyScriptRunRepository(self.session)
        self.script_versions = SqlAlchemyScriptVersionRepository(self.session)
        self.creative_generation_operations = SqlAlchemyCreativeGenerationOperationRepository(
            self.session
        )
        self.storyboard_runs = SqlAlchemyStoryboardRunRepository(self.session)
        self.storyboard_versions = SqlAlchemyStoryboardVersionRepository(self.session)
        self.shot_plan_runs = SqlAlchemyShotPlanRunRepository(self.session)
        self.shot_plan_versions = SqlAlchemyShotPlanVersionRepository(self.session)
        self.visual_planning_operations = SqlAlchemyVisualPlanningOperationRepository(self.session)
        self.audit_events = SqlAlchemyAuditEventRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
