from types import TracebackType
from typing import Protocol, Self

from services.api.app.application.repositories import (
    AuditEventRepository,
    BriefIngestionRepository,
    BriefRepository,
    BriefVersionRepository,
    MembershipRepository,
    OrganizationRepository,
    ProjectRepository,
    RequirementIssueRepository,
    WorkspaceRepository,
)


class UnitOfWork(Protocol):
    organizations: OrganizationRepository
    workspaces: WorkspaceRepository
    memberships: MembershipRepository
    projects: ProjectRepository
    briefs: BriefRepository
    brief_ingestions: BriefIngestionRepository
    brief_versions: BriefVersionRepository
    requirement_issues: RequirementIssueRepository
    audit_events: AuditEventRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
