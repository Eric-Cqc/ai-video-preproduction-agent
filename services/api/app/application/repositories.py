from typing import Protocol
from uuid import UUID

from services.api.app.domain import (
    AuditEvent,
    Brief,
    BriefVersion,
    Membership,
    Organization,
    Project,
    RequirementIssue,
    RequirementIssueStatus,
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
