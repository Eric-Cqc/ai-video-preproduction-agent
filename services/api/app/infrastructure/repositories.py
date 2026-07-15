from uuid import UUID

from sqlalchemy import Select, case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.application.errors import ResourceConflict
from services.api.app.domain import (
    AuditEvent,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
    Project,
    ProjectStatus,
    VersionConflict,
    Workspace,
    WorkspaceStatus,
)
from services.api.app.infrastructure.models import (
    AuditEventRecord,
    MembershipRecord,
    OrganizationRecord,
    ProjectRecord,
    WorkspaceRecord,
)


def _flush_or_conflict(session: Session, code: str, message: str) -> None:
    try:
        session.flush()
    except IntegrityError as error:
        raise ResourceConflict(message, code=code) from error


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, organization: Organization) -> Organization:
        record = OrganizationRecord(
            id=organization.id,
            slug=organization.slug,
            name=organization.name,
            status=organization.status.value,
            created_at=organization.created_at,
            updated_at=organization.updated_at,
            version=organization.version,
        )
        self.session.add(record)
        _flush_or_conflict(
            self.session, "organization_slug_conflict", "organization slug already exists"
        )
        return _organization(record)

    def get(self, organization_id: UUID) -> Organization | None:
        record = self.session.get(OrganizationRecord, organization_id)
        return _organization(record) if record is not None else None


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, workspace: Workspace) -> Workspace:
        record = WorkspaceRecord(
            id=workspace.id,
            organization_id=workspace.organization_id,
            slug=workspace.slug,
            name=workspace.name,
            status=workspace.status.value,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            version=workspace.version,
        )
        self.session.add(record)
        _flush_or_conflict(self.session, "workspace_slug_conflict", "workspace slug already exists")
        return _workspace(record)

    def get(self, organization_id: UUID, workspace_id: UUID) -> Workspace | None:
        record = self.session.scalar(
            select(WorkspaceRecord).where(
                WorkspaceRecord.organization_id == organization_id,
                WorkspaceRecord.id == workspace_id,
            )
        )
        return _workspace(record) if record is not None else None


class SqlAlchemyMembershipRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, membership: Membership) -> Membership:
        record = MembershipRecord(
            id=membership.id,
            organization_id=membership.organization_id,
            workspace_id=membership.workspace_id,
            actor_subject=membership.actor_subject,
            role=membership.role.value,
            status=membership.status.value,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
            version=membership.version,
        )
        self.session.add(record)
        _flush_or_conflict(
            self.session, "membership_conflict", "membership already exists or has invalid scope"
        )
        return _membership(record)

    def find_any_for_organization(
        self, organization_id: UUID, actor_subject: str
    ) -> Membership | None:
        record = self.session.scalar(
            select(MembershipRecord)
            .where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.actor_subject == actor_subject,
                MembershipRecord.status == MembershipStatus.ACTIVE.value,
            )
            .order_by(MembershipRecord.workspace_id.asc().nullsfirst())
            .limit(1)
        )
        return _membership(record) if record is not None else None

    def find_effective(
        self, organization_id: UUID, workspace_id: UUID, actor_subject: str
    ) -> Membership | None:
        record = self.session.scalar(
            select(MembershipRecord)
            .where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.actor_subject == actor_subject,
                MembershipRecord.status == MembershipStatus.ACTIVE.value,
                (MembershipRecord.workspace_id.is_(None))
                | (MembershipRecord.workspace_id == workspace_id),
            )
            .order_by(case((MembershipRecord.workspace_id.is_(None), 0), else_=1))
            .limit(1)
        )
        return _membership(record) if record is not None else None

    def find_organization_wide(
        self, organization_id: UUID, actor_subject: str
    ) -> Membership | None:
        record = self.session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.actor_subject == actor_subject,
                MembershipRecord.workspace_id.is_(None),
                MembershipRecord.status == MembershipStatus.ACTIVE.value,
            )
        )
        return _membership(record) if record is not None else None


class SqlAlchemyProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, project: Project) -> Project:
        record = ProjectRecord(
            id=project.id,
            organization_id=project.organization_id,
            workspace_id=project.workspace_id,
            name=project.name,
            description=project.description,
            status=project.status.value,
            created_by_actor_subject=project.created_by_actor_subject,
            created_at=project.created_at,
            updated_at=project.updated_at,
            version=project.version,
        )
        self.session.add(record)
        _flush_or_conflict(self.session, "project_conflict", "project ownership is invalid")
        return _project(record)

    def get(self, organization_id: UUID, workspace_id: UUID, project_id: UUID) -> Project | None:
        record = self.session.scalar(
            self._scoped_query(organization_id, workspace_id).where(ProjectRecord.id == project_id)
        )
        return _project(record) if record is not None else None

    def list(self, organization_id: UUID, workspace_id: UUID) -> list[Project]:
        records = self.session.scalars(
            self._scoped_query(organization_id, workspace_id).order_by(
                ProjectRecord.created_at, ProjectRecord.id
            )
        ).all()
        return [_project(record) for record in records]

    def update(self, project: Project, *, expected_version: int) -> Project:
        record = self.session.scalar(
            update(ProjectRecord)
            .where(
                ProjectRecord.organization_id == project.organization_id,
                ProjectRecord.workspace_id == project.workspace_id,
                ProjectRecord.id == project.id,
                ProjectRecord.version == expected_version,
            )
            .values(
                name=project.name,
                description=project.description,
                status=project.status.value,
                updated_at=project.updated_at,
                version=project.version,
            )
            .returning(ProjectRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("project version changed before update")
        return _project(record)

    @staticmethod
    def _scoped_query(organization_id: UUID, workspace_id: UUID) -> Select[tuple[ProjectRecord]]:
        return select(ProjectRecord).where(
            ProjectRecord.organization_id == organization_id,
            ProjectRecord.workspace_id == workspace_id,
        )


class SqlAlchemyAuditEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        record = AuditEventRecord(
            id=event.id,
            organization_id=event.organization_id,
            workspace_id=event.workspace_id,
            actor_subject=event.actor_subject,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            action=event.action,
            payload=event.payload,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
        )
        self.session.add(record)
        _flush_or_conflict(self.session, "audit_conflict", "audit event could not be appended")
        return _audit_event(record)

    def list_for_project(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[AuditEvent]:
        records = self.session.scalars(
            select(AuditEventRecord)
            .where(
                AuditEventRecord.organization_id == organization_id,
                AuditEventRecord.workspace_id == workspace_id,
                AuditEventRecord.aggregate_type == "project",
                AuditEventRecord.aggregate_id == project_id,
            )
            .order_by(AuditEventRecord.occurred_at, AuditEventRecord.id)
        ).all()
        return [_audit_event(record) for record in records]


def _organization(record: OrganizationRecord) -> Organization:
    return Organization(
        id=record.id,
        slug=record.slug,
        name=record.name,
        status=OrganizationStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _workspace(record: WorkspaceRecord) -> Workspace:
    return Workspace(
        id=record.id,
        organization_id=record.organization_id,
        slug=record.slug,
        name=record.name,
        status=WorkspaceStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _membership(record: MembershipRecord) -> Membership:
    return Membership(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        actor_subject=record.actor_subject,
        role=MembershipRole(record.role),
        status=MembershipStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _project(record: ProjectRecord) -> Project:
    return Project(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        name=record.name,
        description=record.description,
        status=ProjectStatus(record.status),
        created_by_actor_subject=record.created_by_actor_subject,
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _audit_event(record: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        actor_subject=record.actor_subject,
        aggregate_type=record.aggregate_type,
        aggregate_id=record.aggregate_id,
        action=record.action,
        payload=record.payload,
        occurred_at=record.occurred_at,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
    )
