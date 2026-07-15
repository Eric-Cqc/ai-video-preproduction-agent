from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, case, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.application.errors import ResourceConflict
from services.api.app.domain import (
    AuditEvent,
    Brief,
    BriefIngestion,
    BriefIngestionOperation,
    BriefIngestionSourceAsset,
    BriefIngestionSourceAssetRelationType,
    BriefIngestionSourceType,
    BriefIngestionStatus,
    BriefSourceType,
    BriefStatus,
    BriefVersion,
    BriefVersionLifecycle,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
    Project,
    ProjectStatus,
    RequirementIssue,
    RequirementIssueSeverity,
    RequirementIssueStatus,
    RequirementIssueType,
    SourceAsset,
    SourceAssetMediaType,
    SourceAssetOperation,
    SourceAssetOperationStatus,
    SourceAssetOperationType,
    SourceAssetSourceType,
    SourceAssetStatus,
    SourceAssetVersion,
    VersionConflict,
    Workspace,
    WorkspaceStatus,
)
from services.api.app.infrastructure.models import (
    AuditEventRecord,
    BriefIngestionRecord,
    BriefIngestionSourceAssetRecord,
    BriefRecord,
    BriefVersionRecord,
    MembershipRecord,
    OrganizationRecord,
    ProjectRecord,
    RequirementIssueRecord,
    SourceAssetOperationRecord,
    SourceAssetRecord,
    SourceAssetVersionRecord,
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


class SqlAlchemyBriefRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, brief: Brief) -> Brief:
        record = BriefRecord(
            id=brief.id,
            organization_id=brief.organization_id,
            workspace_id=brief.workspace_id,
            project_id=brief.project_id,
            title=brief.title,
            status=brief.status.value,
            current_version_id=brief.current_version_id,
            latest_version_number=brief.latest_version_number,
            created_by_actor_subject=brief.created_by_actor_subject,
            created_at=brief.created_at,
            updated_at=brief.updated_at,
            version=brief.version,
        )
        self.session.add(record)
        _flush_or_conflict(self.session, "brief_conflict", "brief ownership is invalid")
        return _brief(record)

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> Brief | None:
        record = self.session.scalar(
            self._scoped_query(organization_id, workspace_id, project_id).where(
                BriefRecord.id == brief_id
            )
        )
        return _brief(record) if record is not None else None

    def list(self, organization_id: UUID, workspace_id: UUID, project_id: UUID) -> list[Brief]:
        records = self.session.scalars(
            self._scoped_query(organization_id, workspace_id, project_id).order_by(
                BriefRecord.created_at, BriefRecord.id
            )
        ).all()
        return [_brief(record) for record in records]

    def update(
        self,
        brief: Brief,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> Brief:
        record = self.session.scalar(
            update(BriefRecord)
            .where(
                BriefRecord.organization_id == brief.organization_id,
                BriefRecord.workspace_id == brief.workspace_id,
                BriefRecord.project_id == brief.project_id,
                BriefRecord.id == brief.id,
                BriefRecord.version == expected_version,
                BriefRecord.current_version_id == expected_current_version_id,
            )
            .values(
                status=brief.status.value,
                current_version_id=brief.current_version_id,
                latest_version_number=brief.latest_version_number,
                updated_at=brief.updated_at,
                version=brief.version,
            )
            .returning(BriefRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("brief version or current version changed before update")
        return _brief(record)

    @staticmethod
    def _scoped_query(
        organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> Select[tuple[BriefRecord]]:
        return select(BriefRecord).where(
            BriefRecord.organization_id == organization_id,
            BriefRecord.workspace_id == workspace_id,
            BriefRecord.project_id == project_id,
        )


class SqlAlchemyBriefIngestionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(self, ingestion: BriefIngestion) -> BriefIngestion | None:
        if ingestion.status is not BriefIngestionStatus.RESERVED:
            raise ValueError("only reserved ingestions may be inserted")
        values = {
            "id": ingestion.id,
            "organization_id": ingestion.organization_id,
            "workspace_id": ingestion.workspace_id,
            "project_id": ingestion.project_id,
            "brief_id": ingestion.brief_id,
            "brief_version_id": ingestion.brief_version_id,
            "operation": ingestion.operation.value,
            "idempotency_key": ingestion.idempotency_key,
            "source_type": ingestion.source_type.value,
            "source_reference": ingestion.source_reference,
            "payload_digest": ingestion.payload_digest,
            "schema_version": ingestion.schema_version,
            "status": ingestion.status.value,
            "rejection_code": ingestion.rejection_code,
            "rejection_details": ingestion.rejection_details,
            "submitted_by_actor_subject": ingestion.submitted_by_actor_subject,
            "submitted_at": ingestion.submitted_at,
            "completed_at": ingestion.completed_at,
            "correlation_id": ingestion.correlation_id,
            "version": ingestion.version,
        }
        record = self.session.scalar(
            insert(BriefIngestionRecord)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_brief_ingestions_idempotency")
            .returning(BriefIngestionRecord)
        )
        return _brief_ingestion(record) if record is not None else None

    def finalize_accepted(
        self,
        ingestion: BriefIngestion,
        *,
        brief_id: UUID,
        brief_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> BriefIngestion:
        record = self.session.scalar(
            update(BriefIngestionRecord)
            .where(
                BriefIngestionRecord.organization_id == ingestion.organization_id,
                BriefIngestionRecord.workspace_id == ingestion.workspace_id,
                BriefIngestionRecord.project_id == ingestion.project_id,
                BriefIngestionRecord.id == ingestion.id,
                BriefIngestionRecord.status == BriefIngestionStatus.RESERVED.value,
                BriefIngestionRecord.operation == ingestion.operation.value,
                BriefIngestionRecord.idempotency_key == ingestion.idempotency_key,
                BriefIngestionRecord.payload_digest == ingestion.payload_digest,
                BriefIngestionRecord.version == expected_version,
            )
            .values(
                status=BriefIngestionStatus.ACCEPTED.value,
                brief_id=brief_id,
                brief_version_id=brief_version_id,
                completed_at=completed_at,
                version=expected_version + 1,
            )
            .returning(BriefIngestionRecord)
        )
        if record is None:
            raise VersionConflict("ingestion reservation changed before acceptance")
        return _brief_ingestion(record)

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, ingestion_id: UUID
    ) -> BriefIngestion | None:
        record = self.session.scalar(
            select(BriefIngestionRecord).where(
                BriefIngestionRecord.organization_id == organization_id,
                BriefIngestionRecord.workspace_id == workspace_id,
                BriefIngestionRecord.project_id == project_id,
                BriefIngestionRecord.id == ingestion_id,
            )
        )
        return _brief_ingestion(record) if record is not None else None

    def get_by_idempotency_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: BriefIngestionOperation,
        idempotency_key: str,
    ) -> BriefIngestion | None:
        record = self.session.scalar(
            select(BriefIngestionRecord).where(
                BriefIngestionRecord.organization_id == organization_id,
                BriefIngestionRecord.workspace_id == workspace_id,
                BriefIngestionRecord.project_id == project_id,
                BriefIngestionRecord.operation == operation.value,
                BriefIngestionRecord.idempotency_key == idempotency_key,
            )
        )
        return _brief_ingestion(record) if record is not None else None


class SqlAlchemyBriefIngestionSourceAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_for_accepted_ingestion(
        self, attachment: BriefIngestionSourceAsset
    ) -> BriefIngestionSourceAsset:
        columns = [
            BriefIngestionSourceAssetRecord.id,
            BriefIngestionSourceAssetRecord.organization_id,
            BriefIngestionSourceAssetRecord.workspace_id,
            BriefIngestionSourceAssetRecord.project_id,
            BriefIngestionSourceAssetRecord.brief_ingestion_id,
            BriefIngestionSourceAssetRecord.source_asset_id,
            BriefIngestionSourceAssetRecord.source_asset_version_id,
            BriefIngestionSourceAssetRecord.relation_type,
            BriefIngestionSourceAssetRecord.position,
            BriefIngestionSourceAssetRecord.attached_by_actor_subject,
            BriefIngestionSourceAssetRecord.attached_at,
        ]
        values = select(
            literal(attachment.id),
            literal(attachment.organization_id),
            literal(attachment.workspace_id),
            literal(attachment.project_id),
            literal(attachment.brief_ingestion_id),
            literal(attachment.source_asset_id),
            literal(attachment.source_asset_version_id),
            literal(attachment.relation_type.value),
            literal(attachment.position),
            literal(attachment.attached_by_actor_subject),
            literal(attachment.attached_at),
        ).where(
            BriefIngestionRecord.organization_id == attachment.organization_id,
            BriefIngestionRecord.workspace_id == attachment.workspace_id,
            BriefIngestionRecord.project_id == attachment.project_id,
            BriefIngestionRecord.id == attachment.brief_ingestion_id,
            BriefIngestionRecord.status == BriefIngestionStatus.ACCEPTED.value,
        )
        record = self.session.scalar(
            insert(BriefIngestionSourceAssetRecord)
            .from_select(columns, values)
            .returning(BriefIngestionSourceAssetRecord)
        )
        if record is None:
            raise ResourceConflict(
                "brief ingestion source attachment requires an accepted ingestion",
                code="brief_ingestion_attachment_conflict",
            )
        return _brief_ingestion_source_asset(record)

    def list_for_ingestion(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_ingestion_id: UUID
    ) -> list[BriefIngestionSourceAsset]:
        records = self.session.scalars(
            select(BriefIngestionSourceAssetRecord)
            .where(
                BriefIngestionSourceAssetRecord.organization_id == organization_id,
                BriefIngestionSourceAssetRecord.workspace_id == workspace_id,
                BriefIngestionSourceAssetRecord.project_id == project_id,
                BriefIngestionSourceAssetRecord.brief_ingestion_id == brief_ingestion_id,
            )
            .order_by(BriefIngestionSourceAssetRecord.position)
        ).all()
        return [_brief_ingestion_source_asset(record) for record in records]


class SqlAlchemyBriefVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, version: BriefVersion) -> BriefVersion:
        record = BriefVersionRecord(
            id=version.id,
            organization_id=version.organization_id,
            workspace_id=version.workspace_id,
            project_id=version.project_id,
            brief_id=version.brief_id,
            version_number=version.version_number,
            lifecycle_state=version.lifecycle_state.value,
            structured_content=version.structured_content,
            source_type=version.source_type.value,
            source_reference=version.source_reference,
            change_summary=version.change_summary,
            created_by_actor_subject=version.created_by_actor_subject,
            created_at=version.created_at,
            submitted_for_review_at=version.submitted_for_review_at,
            approved_at=version.approved_at,
            approved_by_actor_subject=version.approved_by_actor_subject,
            supersedes_version_id=version.supersedes_version_id,
            content_schema_version=version.content_schema_version,
        )
        self.session.add(record)
        _flush_or_conflict(self.session, "brief_version_conflict", "brief version is invalid")
        return _brief_version(record)

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> BriefVersion | None:
        record = self.session.scalar(
            self._scoped_query(organization_id, workspace_id, project_id, brief_id).where(
                BriefVersionRecord.id == version_id
            )
        )
        return _brief_version(record) if record is not None else None

    def list(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> list[BriefVersion]:
        records = self.session.scalars(
            self._scoped_query(organization_id, workspace_id, project_id, brief_id).order_by(
                BriefVersionRecord.version_number
            )
        ).all()
        return [_brief_version(record) for record in records]

    def submit_for_review(self, version: BriefVersion) -> BriefVersion:
        record = self.session.scalar(
            update(BriefVersionRecord)
            .where(
                BriefVersionRecord.organization_id == version.organization_id,
                BriefVersionRecord.workspace_id == version.workspace_id,
                BriefVersionRecord.project_id == version.project_id,
                BriefVersionRecord.brief_id == version.brief_id,
                BriefVersionRecord.id == version.id,
                BriefVersionRecord.lifecycle_state == BriefVersionLifecycle.DRAFT.value,
            )
            .values(
                lifecycle_state=BriefVersionLifecycle.IN_REVIEW.value,
                submitted_for_review_at=version.submitted_for_review_at,
            )
            .returning(BriefVersionRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("brief version lifecycle changed before review submission")
        return _brief_version(record)

    def approve(self, version: BriefVersion) -> BriefVersion:
        record = self.session.scalar(
            update(BriefVersionRecord)
            .where(
                BriefVersionRecord.organization_id == version.organization_id,
                BriefVersionRecord.workspace_id == version.workspace_id,
                BriefVersionRecord.project_id == version.project_id,
                BriefVersionRecord.brief_id == version.brief_id,
                BriefVersionRecord.id == version.id,
                BriefVersionRecord.lifecycle_state == BriefVersionLifecycle.IN_REVIEW.value,
            )
            .values(
                lifecycle_state=BriefVersionLifecycle.APPROVED.value,
                approved_at=version.approved_at,
                approved_by_actor_subject=version.approved_by_actor_subject,
            )
            .returning(BriefVersionRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("brief version lifecycle changed before approval")
        return _brief_version(record)

    def supersede(self, version: BriefVersion) -> BriefVersion:
        record = self.session.scalar(
            update(BriefVersionRecord)
            .where(
                BriefVersionRecord.organization_id == version.organization_id,
                BriefVersionRecord.workspace_id == version.workspace_id,
                BriefVersionRecord.project_id == version.project_id,
                BriefVersionRecord.brief_id == version.brief_id,
                BriefVersionRecord.id == version.id,
                BriefVersionRecord.lifecycle_state.in_(
                    [BriefVersionLifecycle.DRAFT.value, BriefVersionLifecycle.IN_REVIEW.value]
                ),
            )
            .values(lifecycle_state=BriefVersionLifecycle.SUPERSEDED.value)
            .returning(BriefVersionRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("approved or stale brief version cannot be superseded")
        return _brief_version(record)

    @staticmethod
    def _scoped_query(
        organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> Select[tuple[BriefVersionRecord]]:
        return select(BriefVersionRecord).where(
            BriefVersionRecord.organization_id == organization_id,
            BriefVersionRecord.workspace_id == workspace_id,
            BriefVersionRecord.project_id == project_id,
            BriefVersionRecord.brief_id == brief_id,
        )


class SqlAlchemySourceAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, asset: SourceAsset) -> SourceAsset:
        record = SourceAssetRecord(
            id=asset.id,
            organization_id=asset.organization_id,
            workspace_id=asset.workspace_id,
            project_id=asset.project_id,
            display_name=asset.display_name,
            status=asset.status.value,
            current_version_id=asset.current_version_id,
            latest_version_number=asset.latest_version_number,
            created_by_actor_subject=asset.created_by_actor_subject,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            version=asset.version,
        )
        self.session.add(record)
        _flush_or_conflict(
            self.session, "source_asset_conflict", "source asset ownership is invalid"
        )
        return _source_asset(record)

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> SourceAsset | None:
        record = self.session.scalar(
            self._scoped_query(organization_id, workspace_id, project_id).where(
                SourceAssetRecord.id == source_asset_id
            )
        )
        return _source_asset(record) if record is not None else None

    def list(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[SourceAsset]:
        records = self.session.scalars(
            self._scoped_query(organization_id, workspace_id, project_id)
            .order_by(SourceAssetRecord.created_at, SourceAssetRecord.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [_source_asset(record) for record in records]

    def compare_and_move_pointer(
        self,
        asset: SourceAsset,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAsset:
        record = self.session.scalar(
            update(SourceAssetRecord)
            .where(
                SourceAssetRecord.organization_id == asset.organization_id,
                SourceAssetRecord.workspace_id == asset.workspace_id,
                SourceAssetRecord.project_id == asset.project_id,
                SourceAssetRecord.id == asset.id,
                SourceAssetRecord.version == expected_version,
                SourceAssetRecord.current_version_id == expected_current_version_id,
                SourceAssetRecord.status == SourceAssetStatus.ACTIVE.value,
            )
            .values(
                current_version_id=asset.current_version_id,
                latest_version_number=SourceAssetRecord.latest_version_number + 1,
                updated_at=asset.updated_at,
                version=SourceAssetRecord.version + 1,
            )
            .returning(SourceAssetRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("source asset version or current pointer changed before update")
        return _source_asset(record)

    def compare_and_archive(
        self,
        asset: SourceAsset,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAsset:
        record = self.session.scalar(
            update(SourceAssetRecord)
            .where(
                SourceAssetRecord.organization_id == asset.organization_id,
                SourceAssetRecord.workspace_id == asset.workspace_id,
                SourceAssetRecord.project_id == asset.project_id,
                SourceAssetRecord.id == asset.id,
                SourceAssetRecord.version == expected_version,
                SourceAssetRecord.current_version_id == expected_current_version_id,
                SourceAssetRecord.status == SourceAssetStatus.ACTIVE.value,
            )
            .values(
                status=SourceAssetStatus.ARCHIVED.value,
                updated_at=asset.updated_at,
                version=SourceAssetRecord.version + 1,
            )
            .returning(SourceAssetRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("source asset could not be archived with the expected pointer")
        return _source_asset(record)

    @staticmethod
    def _scoped_query(
        organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> Select[tuple[SourceAssetRecord]]:
        return select(SourceAssetRecord).where(
            SourceAssetRecord.organization_id == organization_id,
            SourceAssetRecord.workspace_id == workspace_id,
            SourceAssetRecord.project_id == project_id,
        )


class SqlAlchemySourceAssetVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, version: SourceAssetVersion) -> SourceAssetVersion:
        record = SourceAssetVersionRecord(
            id=version.id,
            organization_id=version.organization_id,
            workspace_id=version.workspace_id,
            project_id=version.project_id,
            source_asset_id=version.source_asset_id,
            version_number=version.version_number,
            original_filename=version.original_filename,
            media_type=version.media_type.value,
            byte_size=version.byte_size,
            checksum_algorithm=version.checksum_algorithm,
            checksum_value=version.checksum_value,
            source_type=version.source_type.value,
            source_reference=version.source_reference,
            external_record_id=version.external_record_id,
            declared_created_at=version.declared_created_at,
            created_by_actor_subject=version.created_by_actor_subject,
            created_at=version.created_at,
            supersedes_version_id=version.supersedes_version_id,
            metadata_schema_version=version.metadata_schema_version,
        )
        self.session.add(record)
        _flush_or_conflict(
            self.session, "source_asset_version_conflict", "source asset version is invalid"
        )
        return _source_asset_version(record)

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        version_id: UUID,
    ) -> SourceAssetVersion | None:
        record = self.session.scalar(
            self._scoped_query(organization_id, workspace_id, project_id, source_asset_id).where(
                SourceAssetVersionRecord.id == version_id
            )
        )
        return _source_asset_version(record) if record is not None else None

    def list_for_asset(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> list[SourceAssetVersion]:
        records = self.session.scalars(
            self._scoped_query(organization_id, workspace_id, project_id, source_asset_id).order_by(
                SourceAssetVersionRecord.version_number
            )
        ).all()
        return [_source_asset_version(record) for record in records]

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
    ) -> int:
        query = (
            select(func.count())
            .select_from(SourceAssetVersionRecord)
            .where(
                SourceAssetVersionRecord.organization_id == organization_id,
                SourceAssetVersionRecord.workspace_id == workspace_id,
                SourceAssetVersionRecord.project_id == project_id,
                SourceAssetVersionRecord.checksum_algorithm == checksum_algorithm,
                SourceAssetVersionRecord.checksum_value == checksum_value,
                SourceAssetVersionRecord.byte_size == byte_size,
                SourceAssetVersionRecord.media_type == media_type,
            )
        )
        if exclude_source_asset_id is not None:
            query = query.where(SourceAssetVersionRecord.source_asset_id != exclude_source_asset_id)
        return int(self.session.scalar(query) or 0)

    @staticmethod
    def _scoped_query(
        organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> Select[tuple[SourceAssetVersionRecord]]:
        return select(SourceAssetVersionRecord).where(
            SourceAssetVersionRecord.organization_id == organization_id,
            SourceAssetVersionRecord.workspace_id == workspace_id,
            SourceAssetVersionRecord.project_id == project_id,
            SourceAssetVersionRecord.source_asset_id == source_asset_id,
        )


class SqlAlchemySourceAssetOperationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(self, operation: SourceAssetOperation) -> SourceAssetOperation | None:
        if operation.status is not SourceAssetOperationStatus.RESERVED:
            raise ValueError("only reserved source asset operations may be inserted")
        record = self.session.scalar(
            insert(SourceAssetOperationRecord)
            .values(
                id=operation.id,
                organization_id=operation.organization_id,
                workspace_id=operation.workspace_id,
                project_id=operation.project_id,
                source_asset_id=operation.source_asset_id,
                source_asset_version_id=operation.source_asset_version_id,
                operation=operation.operation.value,
                idempotency_key=operation.idempotency_key,
                request_digest=operation.request_digest,
                status=operation.status.value,
                submitted_by_actor_subject=operation.submitted_by_actor_subject,
                submitted_at=operation.submitted_at,
                completed_at=operation.completed_at,
                correlation_id=operation.correlation_id,
                version=operation.version,
            )
            .on_conflict_do_nothing(constraint="uq_source_asset_operations_idempotency")
            .returning(SourceAssetOperationRecord)
        )
        return _source_asset_operation(record) if record is not None else None

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: SourceAssetOperationType,
        idempotency_key: str,
    ) -> SourceAssetOperation | None:
        record = self.session.scalar(
            select(SourceAssetOperationRecord).where(
                SourceAssetOperationRecord.organization_id == organization_id,
                SourceAssetOperationRecord.workspace_id == workspace_id,
                SourceAssetOperationRecord.project_id == project_id,
                SourceAssetOperationRecord.operation == operation.value,
                SourceAssetOperationRecord.idempotency_key == idempotency_key,
            )
        )
        return _source_asset_operation(record) if record is not None else None

    def finalize_accepted(
        self,
        operation: SourceAssetOperation,
        *,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> SourceAssetOperation:
        record = self.session.scalar(
            update(SourceAssetOperationRecord)
            .where(
                SourceAssetOperationRecord.organization_id == operation.organization_id,
                SourceAssetOperationRecord.workspace_id == operation.workspace_id,
                SourceAssetOperationRecord.project_id == operation.project_id,
                SourceAssetOperationRecord.id == operation.id,
                SourceAssetOperationRecord.status == SourceAssetOperationStatus.RESERVED.value,
                SourceAssetOperationRecord.operation == operation.operation.value,
                SourceAssetOperationRecord.idempotency_key == operation.idempotency_key,
                SourceAssetOperationRecord.request_digest == operation.request_digest,
                SourceAssetOperationRecord.version == expected_version,
            )
            .values(
                status=SourceAssetOperationStatus.ACCEPTED.value,
                source_asset_id=source_asset_id,
                source_asset_version_id=source_asset_version_id,
                completed_at=completed_at,
                version=expected_version + 1,
            )
            .returning(SourceAssetOperationRecord)
        )
        if record is None:
            raise VersionConflict("source asset operation changed before acceptance")
        return _source_asset_operation(record)


class SqlAlchemyRequirementIssueRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, issue: RequirementIssue) -> RequirementIssue:
        record = RequirementIssueRecord(
            id=issue.id,
            organization_id=issue.organization_id,
            workspace_id=issue.workspace_id,
            project_id=issue.project_id,
            brief_id=issue.brief_id,
            brief_version_id=issue.brief_version_id,
            issue_type=issue.issue_type.value,
            field_path=issue.field_path,
            severity=issue.severity.value,
            message=issue.message,
            status=issue.status.value,
            resolution_note=issue.resolution_note,
            created_by_actor_subject=issue.created_by_actor_subject,
            resolved_by_actor_subject=issue.resolved_by_actor_subject,
            created_at=issue.created_at,
            resolved_at=issue.resolved_at,
            version=issue.version,
        )
        self.session.add(record)
        _flush_or_conflict(self.session, "requirement_issue_conflict", "issue is invalid")
        return _requirement_issue(record)

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        issue_id: UUID,
    ) -> RequirementIssue | None:
        record = self.session.scalar(
            self._scoped_query(
                organization_id, workspace_id, project_id, brief_id, version_id
            ).where(RequirementIssueRecord.id == issue_id)
        )
        return _requirement_issue(record) if record is not None else None

    def list(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> list[RequirementIssue]:
        records = self.session.scalars(
            self._scoped_query(
                organization_id, workspace_id, project_id, brief_id, version_id
            ).order_by(RequirementIssueRecord.created_at, RequirementIssueRecord.id)
        ).all()
        return [_requirement_issue(record) for record in records]

    def count_open_blocking(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> int:
        count = self.session.scalar(
            select(func.count())
            .select_from(RequirementIssueRecord)
            .where(
                RequirementIssueRecord.organization_id == organization_id,
                RequirementIssueRecord.workspace_id == workspace_id,
                RequirementIssueRecord.project_id == project_id,
                RequirementIssueRecord.brief_id == brief_id,
                RequirementIssueRecord.brief_version_id == version_id,
                RequirementIssueRecord.status == RequirementIssueStatus.OPEN.value,
                RequirementIssueRecord.severity == RequirementIssueSeverity.BLOCKING.value,
            )
        )
        return int(count or 0)

    def update(
        self,
        issue: RequirementIssue,
        *,
        expected_version: int,
        expected_status: RequirementIssueStatus,
    ) -> RequirementIssue:
        record = self.session.scalar(
            update(RequirementIssueRecord)
            .where(
                RequirementIssueRecord.organization_id == issue.organization_id,
                RequirementIssueRecord.workspace_id == issue.workspace_id,
                RequirementIssueRecord.project_id == issue.project_id,
                RequirementIssueRecord.brief_id == issue.brief_id,
                RequirementIssueRecord.brief_version_id == issue.brief_version_id,
                RequirementIssueRecord.id == issue.id,
                RequirementIssueRecord.version == expected_version,
                RequirementIssueRecord.status == expected_status.value,
            )
            .values(
                status=issue.status.value,
                resolution_note=issue.resolution_note,
                resolved_by_actor_subject=issue.resolved_by_actor_subject,
                resolved_at=issue.resolved_at,
                version=issue.version,
            )
            .returning(RequirementIssueRecord)
            .execution_options(synchronize_session=False)
        )
        if record is None:
            raise VersionConflict("requirement issue changed before update")
        return _requirement_issue(record)

    @staticmethod
    def _scoped_query(
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> Select[tuple[RequirementIssueRecord]]:
        return select(RequirementIssueRecord).where(
            RequirementIssueRecord.organization_id == organization_id,
            RequirementIssueRecord.workspace_id == workspace_id,
            RequirementIssueRecord.project_id == project_id,
            RequirementIssueRecord.brief_id == brief_id,
            RequirementIssueRecord.brief_version_id == version_id,
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

    def list_for_brief(
        self, organization_id: UUID, workspace_id: UUID, brief_id: UUID
    ) -> list[AuditEvent]:
        records = self.session.scalars(
            select(AuditEventRecord)
            .where(
                AuditEventRecord.organization_id == organization_id,
                AuditEventRecord.workspace_id == workspace_id,
                AuditEventRecord.aggregate_type == "brief",
                AuditEventRecord.aggregate_id == brief_id,
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


def _brief(record: BriefRecord) -> Brief:
    return Brief(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        title=record.title,
        status=BriefStatus(record.status),
        current_version_id=record.current_version_id,
        latest_version_number=record.latest_version_number,
        created_by_actor_subject=record.created_by_actor_subject,
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _brief_ingestion(record: BriefIngestionRecord) -> BriefIngestion:
    return BriefIngestion(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        brief_id=record.brief_id,
        brief_version_id=record.brief_version_id,
        operation=BriefIngestionOperation(record.operation),
        idempotency_key=record.idempotency_key,
        source_type=BriefIngestionSourceType(record.source_type),
        source_reference=record.source_reference,
        payload_digest=record.payload_digest,
        schema_version=record.schema_version,
        status=BriefIngestionStatus(record.status),
        rejection_code=record.rejection_code,
        rejection_details=record.rejection_details,
        submitted_by_actor_subject=record.submitted_by_actor_subject,
        submitted_at=record.submitted_at,
        completed_at=record.completed_at,
        correlation_id=record.correlation_id,
        version=record.version,
    )


def _brief_ingestion_source_asset(
    record: BriefIngestionSourceAssetRecord,
) -> BriefIngestionSourceAsset:
    return BriefIngestionSourceAsset(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        brief_ingestion_id=record.brief_ingestion_id,
        source_asset_id=record.source_asset_id,
        source_asset_version_id=record.source_asset_version_id,
        relation_type=BriefIngestionSourceAssetRelationType(record.relation_type),
        position=record.position,
        attached_by_actor_subject=record.attached_by_actor_subject,
        attached_at=record.attached_at,
    )


def _brief_version(record: BriefVersionRecord) -> BriefVersion:
    return BriefVersion(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        brief_id=record.brief_id,
        version_number=record.version_number,
        lifecycle_state=BriefVersionLifecycle(record.lifecycle_state),
        structured_content=record.structured_content,
        source_type=BriefSourceType(record.source_type),
        source_reference=record.source_reference,
        change_summary=record.change_summary,
        created_by_actor_subject=record.created_by_actor_subject,
        created_at=record.created_at,
        submitted_for_review_at=record.submitted_for_review_at,
        approved_at=record.approved_at,
        approved_by_actor_subject=record.approved_by_actor_subject,
        supersedes_version_id=record.supersedes_version_id,
        content_schema_version=record.content_schema_version,
    )


def _source_asset(record: SourceAssetRecord) -> SourceAsset:
    return SourceAsset(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        display_name=record.display_name,
        status=SourceAssetStatus(record.status),
        current_version_id=record.current_version_id,
        latest_version_number=record.latest_version_number,
        created_by_actor_subject=record.created_by_actor_subject,
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def _source_asset_version(record: SourceAssetVersionRecord) -> SourceAssetVersion:
    return SourceAssetVersion(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        source_asset_id=record.source_asset_id,
        version_number=record.version_number,
        original_filename=record.original_filename,
        media_type=SourceAssetMediaType(record.media_type),
        byte_size=record.byte_size,
        checksum_algorithm=record.checksum_algorithm,
        checksum_value=record.checksum_value,
        source_type=SourceAssetSourceType(record.source_type),
        source_reference=record.source_reference,
        external_record_id=record.external_record_id,
        declared_created_at=record.declared_created_at,
        created_by_actor_subject=record.created_by_actor_subject,
        created_at=record.created_at,
        supersedes_version_id=record.supersedes_version_id,
        metadata_schema_version=record.metadata_schema_version,
    )


def _source_asset_operation(record: SourceAssetOperationRecord) -> SourceAssetOperation:
    return SourceAssetOperation(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        source_asset_id=record.source_asset_id,
        source_asset_version_id=record.source_asset_version_id,
        operation=SourceAssetOperationType(record.operation),
        idempotency_key=record.idempotency_key,
        request_digest=record.request_digest,
        status=SourceAssetOperationStatus(record.status),
        submitted_by_actor_subject=record.submitted_by_actor_subject,
        submitted_at=record.submitted_at,
        completed_at=record.completed_at,
        correlation_id=record.correlation_id,
        version=record.version,
    )


def _requirement_issue(record: RequirementIssueRecord) -> RequirementIssue:
    return RequirementIssue(
        id=record.id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        brief_id=record.brief_id,
        brief_version_id=record.brief_version_id,
        issue_type=RequirementIssueType(record.issue_type),
        field_path=record.field_path,
        severity=RequirementIssueSeverity(record.severity),
        message=record.message,
        status=RequirementIssueStatus(record.status),
        resolution_note=record.resolution_note,
        created_by_actor_subject=record.created_by_actor_subject,
        resolved_by_actor_subject=record.resolved_by_actor_subject,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
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
