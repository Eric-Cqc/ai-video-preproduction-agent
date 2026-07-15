from types import TracebackType

from sqlalchemy.orm import Session

from services.api.app.application.repositories import (
    AuditEventRepository,
    BriefIngestionRepository,
    BriefIngestionSourceAssetRepository,
    BriefRepository,
    BriefVersionRepository,
    MembershipRepository,
    OrganizationRepository,
    ProjectRepository,
    RequirementIssueRepository,
    SourceAssetOperationRepository,
    SourceAssetRepository,
    SourceAssetVersionRepository,
    WorkspaceRepository,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyBriefIngestionRepository,
    SqlAlchemyBriefIngestionSourceAssetRepository,
    SqlAlchemyBriefRepository,
    SqlAlchemyBriefVersionRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyRequirementIssueRepository,
    SqlAlchemySourceAssetOperationRepository,
    SqlAlchemySourceAssetRepository,
    SqlAlchemySourceAssetVersionRepository,
    SqlAlchemyWorkspaceRepository,
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
