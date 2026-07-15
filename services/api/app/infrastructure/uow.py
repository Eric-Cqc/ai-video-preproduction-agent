from types import TracebackType

from sqlalchemy.orm import Session

from services.api.app.application.repositories import (
    AuditEventRepository,
    BriefRepository,
    BriefVersionRepository,
    MembershipRepository,
    OrganizationRepository,
    ProjectRepository,
    RequirementIssueRepository,
    WorkspaceRepository,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyBriefRepository,
    SqlAlchemyBriefVersionRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyRequirementIssueRepository,
    SqlAlchemyWorkspaceRepository,
)


class SqlAlchemyUnitOfWork:
    organizations: OrganizationRepository
    workspaces: WorkspaceRepository
    memberships: MembershipRepository
    projects: ProjectRepository
    briefs: BriefRepository
    brief_versions: BriefVersionRepository
    requirement_issues: RequirementIssueRepository
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
        self.brief_versions = SqlAlchemyBriefVersionRepository(self.session)
        self.requirement_issues = SqlAlchemyRequirementIssueRepository(self.session)
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
