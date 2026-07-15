from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from services.api.app.application.context import (
    ActorContext,
    OrganizationContext,
    TenantContext,
)
from services.api.app.application.errors import InvalidRequest, ResourceNotFound
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    AuditEvent,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
    Project,
    ProjectStatus,
    Workspace,
    WorkspaceStatus,
)

UnitOfWorkFactory = Callable[[], UnitOfWork]
Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]

READ_ROLES = frozenset(MembershipRole)
MUTATION_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER})
ADMIN_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


def utc_now() -> datetime:
    return datetime.now(UTC)


class TenantApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.clock = clock
        self.id_factory = id_factory

    def create_organization(self, context: ActorContext, *, slug: str, name: str) -> Organization:
        now = self.clock()
        organization = Organization(
            id=self.id_factory(),
            slug=slug,
            name=name,
            status=OrganizationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            version=1,
        )
        owner = Membership(
            id=self.id_factory(),
            organization_id=organization.id,
            workspace_id=None,
            actor_subject=context.actor_subject,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            version=1,
        )
        with self.uow_factory() as uow:
            result = uow.organizations.add(organization)
            uow.memberships.add(owner)
            uow.audit_events.append(
                self._event(
                    context,
                    organization_id=organization.id,
                    workspace_id=None,
                    aggregate_type="organization",
                    aggregate_id=organization.id,
                    action="organization.created",
                    payload={"version": 1},
                    occurred_at=now,
                )
            )
            return result

    def get_organization(self, context: OrganizationContext) -> Organization:
        with self.uow_factory() as uow:
            organization = self._require_active_organization(uow, context.organization_id)
            membership = uow.memberships.find_any_for_organization(
                context.organization_id, context.actor_subject
            )
            if membership is None:
                raise ResourceNotFound("organization is not accessible")
            return organization

    def create_workspace(self, context: OrganizationContext, *, slug: str, name: str) -> Workspace:
        now = self.clock()
        workspace = Workspace(
            id=self.id_factory(),
            organization_id=context.organization_id,
            slug=slug,
            name=name,
            status=WorkspaceStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            version=1,
        )
        with self.uow_factory() as uow:
            self._require_active_organization(uow, context.organization_id)
            membership = uow.memberships.find_organization_wide(
                context.organization_id, context.actor_subject
            )
            self._require_role(membership, ADMIN_ROLES)
            result = uow.workspaces.add(workspace)
            uow.audit_events.append(
                self._event(
                    context,
                    organization_id=context.organization_id,
                    workspace_id=workspace.id,
                    aggregate_type="workspace",
                    aggregate_id=workspace.id,
                    action="workspace.created",
                    payload={"version": 1},
                    occurred_at=now,
                )
            )
            return result

    def get_workspace(self, context: TenantContext) -> Workspace:
        with self.uow_factory() as uow:
            workspace, _ = self._require_workspace_access(uow, context, READ_ROLES)
            return workspace

    def create_membership(
        self,
        context: TenantContext,
        *,
        actor_subject: str,
        role: MembershipRole,
    ) -> Membership:
        if role is MembershipRole.OWNER:
            raise InvalidRequest("workspace membership cannot use owner role")
        now = self.clock()
        membership = Membership(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            actor_subject=actor_subject,
            role=role,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            version=1,
        )
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, ADMIN_ROLES)
            result = uow.memberships.add(membership)
            uow.audit_events.append(
                self._event(
                    context,
                    organization_id=context.organization_id,
                    workspace_id=context.workspace_id,
                    aggregate_type="membership",
                    aggregate_id=membership.id,
                    action="membership.created",
                    payload={"role": role.value, "version": 1},
                    occurred_at=now,
                )
            )
            return result

    def create_project(
        self, context: TenantContext, *, name: str, description: str | None
    ) -> Project:
        now = self.clock()
        project = Project(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            name=name,
            description=description,
            status=ProjectStatus.DRAFT,
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            updated_at=now,
            version=1,
        )
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, MUTATION_ROLES)
            result = uow.projects.add(project)
            uow.audit_events.append(
                self._project_event(context, result, "project.created", {"version": 1}, now)
            )
            return result

    def get_project(self, context: TenantContext, project_id: UUID) -> Project:
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, READ_ROLES)
            return self._require_project(uow, context, project_id)

    def list_projects(self, context: TenantContext) -> list[Project]:
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, READ_ROLES)
            return uow.projects.list(context.organization_id, context.workspace_id)

    def update_project(
        self,
        context: TenantContext,
        project_id: UUID,
        *,
        expected_version: int,
        changed_fields: frozenset[str],
        name: str | None,
        description: str | None,
    ) -> Project:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, MUTATION_ROLES)
            current = self._require_project(uow, context, project_id)
            updated = current.update_details(
                expected_version=expected_version,
                changed_fields=changed_fields,
                name=name,
                description=description,
                now=now,
            )
            result = uow.projects.update(updated, expected_version=expected_version)
            uow.audit_events.append(
                self._project_event(
                    context,
                    result,
                    "project.updated",
                    {"changed_fields": sorted(changed_fields), "version": result.version},
                    now,
                )
            )
            return result

    def activate_project(
        self, context: TenantContext, project_id: UUID, *, expected_version: int
    ) -> Project:
        return self._transition_project(
            context, project_id, expected_version, action="project.activated"
        )

    def archive_project(
        self, context: TenantContext, project_id: UUID, *, expected_version: int
    ) -> Project:
        return self._transition_project(
            context, project_id, expected_version, action="project.archived"
        )

    def list_project_audit_events(
        self, context: TenantContext, project_id: UUID
    ) -> list[AuditEvent]:
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, READ_ROLES)
            self._require_project(uow, context, project_id)
            return uow.audit_events.list_for_project(
                context.organization_id, context.workspace_id, project_id
            )

    def _transition_project(
        self,
        context: TenantContext,
        project_id: UUID,
        expected_version: int,
        *,
        action: str,
    ) -> Project:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_workspace_access(uow, context, MUTATION_ROLES)
            current = self._require_project(uow, context, project_id)
            updated = (
                current.activate(expected_version=expected_version, now=now)
                if action == "project.activated"
                else current.archive(expected_version=expected_version, now=now)
            )
            result = uow.projects.update(updated, expected_version=expected_version)
            uow.audit_events.append(
                self._project_event(
                    context,
                    result,
                    action,
                    {
                        "from_status": current.status.value,
                        "to_status": result.status.value,
                        "version": result.version,
                    },
                    now,
                )
            )
            return result

    @staticmethod
    def _require_active_organization(uow: UnitOfWork, organization_id: UUID) -> Organization:
        organization = uow.organizations.get(organization_id)
        if organization is None or organization.status is not OrganizationStatus.ACTIVE:
            raise ResourceNotFound("organization is not accessible")
        return organization

    def _require_workspace_access(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        allowed_roles: frozenset[MembershipRole],
    ) -> tuple[Workspace, Membership]:
        self._require_active_organization(uow, context.organization_id)
        workspace = uow.workspaces.get(context.organization_id, context.workspace_id)
        if workspace is None or workspace.status is not WorkspaceStatus.ACTIVE:
            raise ResourceNotFound("workspace is not accessible")
        membership = uow.memberships.find_effective(
            context.organization_id, context.workspace_id, context.actor_subject
        )
        self._require_role(membership, allowed_roles)
        assert membership is not None
        return workspace, membership

    @staticmethod
    def _require_role(
        membership: Membership | None, allowed_roles: frozenset[MembershipRole]
    ) -> None:
        if membership is None or membership.role not in allowed_roles:
            raise ResourceNotFound("resource is not accessible")

    @staticmethod
    def _require_project(uow: UnitOfWork, context: TenantContext, project_id: UUID) -> Project:
        project = uow.projects.get(context.organization_id, context.workspace_id, project_id)
        if project is None:
            raise ResourceNotFound("project is not accessible")
        return project

    def _project_event(
        self,
        context: TenantContext,
        project: Project,
        action: str,
        payload: dict[str, object],
        occurred_at: datetime,
    ) -> AuditEvent:
        return self._event(
            context,
            organization_id=project.organization_id,
            workspace_id=project.workspace_id,
            aggregate_type="project",
            aggregate_id=project.id,
            action=action,
            payload=payload,
            occurred_at=occurred_at,
        )

    def _event(
        self,
        context: ActorContext,
        *,
        organization_id: UUID,
        workspace_id: UUID | None,
        aggregate_type: str,
        aggregate_id: UUID,
        action: str,
        payload: dict[str, object],
        occurred_at: datetime,
    ) -> AuditEvent:
        return AuditEvent(
            id=self.id_factory(),
            organization_id=organization_id,
            workspace_id=workspace_id,
            actor_subject=context.actor_subject,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            action=action,
            payload=payload,
            occurred_at=occurred_at,
            correlation_id=context.correlation_id,
        )
