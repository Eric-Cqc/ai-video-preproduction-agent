from typing import Protocol
from uuid import UUID

from services.api.app.domain import AuditEvent, Membership, Organization, Project, Workspace


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


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...

    def list_for_project(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[AuditEvent]: ...
