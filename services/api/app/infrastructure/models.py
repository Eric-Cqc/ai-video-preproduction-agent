from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrganizationRecord(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'archived')", name="ck_org_status"),
        CheckConstraint("version >= 1", name="ck_org_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class WorkspaceRecord(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_workspaces_org_id_id"),
        UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'archived')", name="ck_workspace_status"
        ),
        CheckConstraint("version >= 1", name="ck_workspace_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class MembershipRecord(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_memberships_workspace_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(workspace_id IS NULL AND role IN ('owner', 'admin')) OR "
            "(workspace_id IS NOT NULL AND role IN ('admin', 'member', 'viewer'))",
            name="ck_membership_scope_role",
        ),
        CheckConstraint("status IN ('active', 'suspended')", name="ck_membership_status"),
        CheckConstraint("version >= 1", name="ck_membership_version"),
        Index(
            "uq_memberships_org_actor",
            "organization_id",
            "actor_subject",
            unique=True,
            postgresql_where=text("workspace_id IS NULL"),
        ),
        Index(
            "uq_memberships_workspace_actor",
            "organization_id",
            "workspace_id",
            "actor_subject",
            unique=True,
            postgresql_where=text("workspace_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ProjectRecord(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_projects_tenant_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_projects_workspace_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_project_status"),
        CheckConstraint("version >= 1", name="ck_project_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class BriefRecord(Base):
    __tablename__ = "briefs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_briefs_tenant_project_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_briefs_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "id",
                "current_version_id",
            ],
            [
                "brief_versions.organization_id",
                "brief_versions.workspace_id",
                "brief_versions.project_id",
                "brief_versions.brief_id",
                "brief_versions.id",
            ],
            name="fk_briefs_current_version",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'archived')",
            name="ck_brief_status",
        ),
        CheckConstraint("latest_version_number >= 1", name="ck_brief_latest_version"),
        CheckConstraint("version >= 1", name="ck_brief_version"),
        Index(
            "ix_briefs_tenant_project",
            "organization_id",
            "workspace_id",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    latest_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class BriefVersionRecord(Base):
    __tablename__ = "brief_versions"
    __table_args__ = (
        UniqueConstraint("brief_id", "version_number", name="uq_brief_versions_number"),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_id",
            "id",
            name="uq_brief_versions_tenant_brief_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id"],
            [
                "briefs.organization_id",
                "briefs.workspace_id",
                "briefs.project_id",
                "briefs.id",
            ],
            name="fk_brief_versions_brief_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "brief_id",
                "supersedes_version_id",
            ],
            [
                "brief_versions.organization_id",
                "brief_versions.workspace_id",
                "brief_versions.project_id",
                "brief_versions.brief_id",
                "brief_versions.id",
            ],
            name="fk_brief_versions_supersedes",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number >= 1", name="ck_brief_version_number"),
        CheckConstraint(
            "lifecycle_state IN ('draft', 'in_review', 'approved', 'superseded')",
            name="ck_brief_version_lifecycle",
        ),
        CheckConstraint(
            "source_type IN ('manual', 'imported_structured')",
            name="ck_brief_version_source_type",
        ),
        CheckConstraint("content_schema_version = '1.0.0'", name="ck_brief_content_schema_version"),
        CheckConstraint(
            "(approved_at IS NULL) = (approved_by_actor_subject IS NULL)",
            name="ck_brief_version_approval_pair",
        ),
        CheckConstraint(
            "(lifecycle_state = 'draft' AND submitted_for_review_at IS NULL "
            "AND approved_at IS NULL) OR "
            "(lifecycle_state = 'in_review' AND submitted_for_review_at IS NOT NULL "
            "AND approved_at IS NULL) OR "
            "(lifecycle_state = 'approved' AND submitted_for_review_at IS NOT NULL "
            "AND approved_at IS NOT NULL) OR lifecycle_state = 'superseded'",
            name="ck_brief_version_lifecycle_metadata",
        ),
        Index(
            "ix_brief_versions_tenant_brief",
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(20), nullable=False)
    structured_content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_for_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_actor_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supersedes_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    content_schema_version: Mapped[str] = mapped_column(String(20), nullable=False)


class RequirementIssueRecord(Base):
    __tablename__ = "requirement_issues"
    __table_args__ = (
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "brief_id",
                "brief_version_id",
            ],
            [
                "brief_versions.organization_id",
                "brief_versions.workspace_id",
                "brief_versions.project_id",
                "brief_versions.brief_id",
                "brief_versions.id",
            ],
            name="fk_requirement_issues_version_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "issue_type IN ('missing', 'ambiguous', 'conflicting', 'invalid', 'compliance_risk')",
            name="ck_requirement_issue_type",
        ),
        CheckConstraint(
            "severity IN ('blocking', 'warning', 'informational')",
            name="ck_requirement_issue_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_requirement_issue_status",
        ),
        CheckConstraint("version >= 1", name="ck_requirement_issue_version"),
        CheckConstraint(
            "(status = 'open' AND resolution_note IS NULL "
            "AND resolved_by_actor_subject IS NULL AND resolved_at IS NULL) OR "
            "(status IN ('resolved', 'dismissed') AND resolution_note IS NOT NULL "
            "AND resolved_by_actor_subject IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_requirement_issue_resolution",
        ),
        Index(
            "ix_requirement_issues_tenant_version",
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_id",
            "brief_version_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(30), nullable=False)
    field_path: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    resolved_by_actor_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class BriefIngestionRecord(Base):
    __tablename__ = "brief_ingestions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_brief_ingestions_tenant_project_id",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_brief_ingestions_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_brief_ingestions_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id"],
            ["briefs.organization_id", "briefs.workspace_id", "briefs.project_id", "briefs.id"],
            name="fk_brief_ingestions_brief_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id", "brief_version_id"],
            [
                "brief_versions.organization_id",
                "brief_versions.workspace_id",
                "brief_versions.project_id",
                "brief_versions.brief_id",
                "brief_versions.id",
            ],
            name="fk_brief_ingestions_version_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "operation IN ('create_brief', 'create_version')", name="ck_brief_ingestion_operation"
        ),
        CheckConstraint(
            "source_type IN ('imported_structured', 'api_structured')",
            name="ck_brief_ingestion_source_type",
        ),
        CheckConstraint(
            "status IN ('reserved', 'accepted', 'rejected')", name="ck_brief_ingestion_status"
        ),
        CheckConstraint("payload_digest ~ '^[0-9a-f]{64}$'", name="ck_brief_ingestion_digest"),
        CheckConstraint("schema_version = '1.0.0'", name="ck_brief_ingestion_schema_version"),
        CheckConstraint("version >= 1", name="ck_brief_ingestion_version"),
        CheckConstraint(
            "(status = 'reserved' AND brief_id IS NULL AND brief_version_id IS NULL "
            "AND completed_at IS NULL AND rejection_code IS NULL AND rejection_details IS NULL) OR "
            "(status = 'accepted' AND brief_id IS NOT NULL AND brief_version_id IS NOT NULL "
            "AND completed_at IS NOT NULL AND rejection_code IS NULL "
            "AND rejection_details IS NULL) OR (status = 'rejected' AND brief_id IS NULL "
            "AND brief_version_id IS NULL)",
            name="ck_brief_ingestion_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    brief_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rejection_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rejection_details: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class BriefIngestionSourceAssetRecord(Base):
    __tablename__ = "brief_ingestion_source_assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_ingestion_id"],
            [
                "brief_ingestions.organization_id",
                "brief_ingestions.workspace_id",
                "brief_ingestions.project_id",
                "brief_ingestions.id",
            ],
            name="fk_brief_ingestion_source_assets_ingestion_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_asset_id"],
            [
                "source_assets.organization_id",
                "source_assets.workspace_id",
                "source_assets.project_id",
                "source_assets.id",
            ],
            name="fk_brief_ingestion_source_assets_asset_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "source_asset_id",
                "source_asset_version_id",
            ],
            [
                "source_asset_versions.organization_id",
                "source_asset_versions.workspace_id",
                "source_asset_versions.project_id",
                "source_asset_versions.source_asset_id",
                "source_asset_versions.id",
            ],
            name="fk_brief_ingestion_source_assets_version_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "relation_type IN ('primary_source', 'supporting_source', 'reference')",
            name="ck_brief_ingestion_source_asset_relation_type",
        ),
        CheckConstraint("position >= 0", name="ck_brief_ingestion_source_asset_position"),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_ingestion_id",
            "position",
            name="uq_brief_ingestion_source_assets_position",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_ingestion_id",
            "source_asset_version_id",
            "relation_type",
            name="uq_brief_ingestion_source_assets_version_relation",
        ),
        Index(
            "ix_brief_ingestion_source_assets_ingestion",
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_ingestion_id",
            "position",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_ingestion_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    attached_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    attached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceAssetRecord(Base):
    __tablename__ = "source_assets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_source_assets_tenant_project_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_source_assets_workspace_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_source_assets_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "id",
                "current_version_id",
            ],
            [
                "source_asset_versions.organization_id",
                "source_asset_versions.workspace_id",
                "source_asset_versions.project_id",
                "source_asset_versions.source_asset_id",
                "source_asset_versions.id",
            ],
            name="fk_source_assets_current_version",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        CheckConstraint("status IN ('active', 'archived')", name="ck_source_asset_status"),
        CheckConstraint("latest_version_number >= 1", name="ck_source_asset_latest_version"),
        CheckConstraint("version >= 1", name="ck_source_asset_version"),
        CheckConstraint(
            "length(btrim(display_name)) > 0 AND display_name !~ '[[:cntrl:]]'",
            name="ck_source_asset_display_name",
        ),
        Index(
            "ix_source_assets_tenant_project",
            "organization_id",
            "workspace_id",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    latest_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class SourceAssetVersionRecord(Base):
    __tablename__ = "source_asset_versions"
    __table_args__ = (
        UniqueConstraint(
            "source_asset_id", "version_number", name="uq_source_asset_versions_number"
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "id",
            name="uq_source_asset_versions_tenant_asset_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_asset_id"],
            [
                "source_assets.organization_id",
                "source_assets.workspace_id",
                "source_assets.project_id",
                "source_assets.id",
            ],
            name="fk_source_asset_versions_asset_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "source_asset_id",
                "supersedes_version_id",
            ],
            [
                "source_asset_versions.organization_id",
                "source_asset_versions.workspace_id",
                "source_asset_versions.project_id",
                "source_asset_versions.source_asset_id",
                "source_asset_versions.id",
            ],
            name="fk_source_asset_versions_supersedes",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number >= 1", name="ck_source_asset_version_number"),
        CheckConstraint(
            "byte_size > 0 AND byte_size <= 104857600",
            name="ck_source_asset_version_byte_size",
        ),
        CheckConstraint(
            "checksum_algorithm = 'sha256'", name="ck_source_asset_version_checksum_algorithm"
        ),
        CheckConstraint(
            "checksum_value ~ '^[0-9a-f]{64}$'",
            name="ck_source_asset_version_checksum_value",
        ),
        CheckConstraint(
            "media_type IN ('application/pdf', "
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', "
            "'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', "
            "'text/plain', 'text/csv', 'application/json')",
            name="ck_source_asset_version_media_type",
        ),
        CheckConstraint(
            "source_type IN ('manual_metadata', 'external_system', 'api_declared')",
            name="ck_source_asset_version_source_type",
        ),
        CheckConstraint(
            "metadata_schema_version = '1.0.0'",
            name="ck_source_asset_version_metadata_schema_version",
        ),
        CheckConstraint(
            "length(btrim(original_filename)) > 0 AND "
            "original_filename !~ '[[:cntrl:]/\\\\]' AND original_filename NOT LIKE '%..%'",
            name="ck_source_asset_version_filename",
        ),
        CheckConstraint(
            "(source_reference IS NULL OR (length(btrim(source_reference)) > 0 AND "
            "source_reference !~ '[[:cntrl:]]' AND "
            "source_reference !~ '(^/|^~/|^[A-Za-z]:\\\\|^\\\\\\\\|^file://|"
            "^postgres(ql)?://|^mysql://|^mongodb(\\\\+srv)?://|"
            "^[A-Za-z][A-Za-z0-9+.-]*://[^/[:space:]]*@)' AND "
            "source_reference !~* '(authorization|bearer|token|access[_-]?token|"
            "refresh[_-]?token|api[_-]?key|secret|password|"
            "(\\\\?|&)(x-amz-signature|x-goog-signature|signature|sig|token|"
            "access_token)=)'))",
            name="ck_source_asset_version_source_reference",
        ),
        CheckConstraint(
            "(external_record_id IS NULL OR (length(btrim(external_record_id)) > 0 AND "
            "external_record_id !~ '[[:cntrl:]]' AND "
            "external_record_id !~ '(^/|^~/|^[A-Za-z]:\\\\|^\\\\\\\\|^file://|"
            "^postgres(ql)?://|^mysql://|^mongodb(\\\\+srv)?://|"
            "^[A-Za-z][A-Za-z0-9+.-]*://[^/[:space:]]*@)' AND "
            "external_record_id !~* '(authorization|bearer|token|access[_-]?token|"
            "refresh[_-]?token|api[_-]?key|secret|password|"
            "(\\\\?|&)(x-amz-signature|x-goog-signature|signature|sig|token|"
            "access_token)=)'))",
            name="ck_source_asset_version_external_record_id",
        ),
        Index(
            "ix_source_asset_versions_tenant_asset",
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_algorithm: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum_value: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_record_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    declared_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    supersedes_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    metadata_schema_version: Mapped[str] = mapped_column(String(20), nullable=False)


class SourceAssetOperationRecord(Base):
    __tablename__ = "source_asset_operations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_source_asset_operations_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_source_asset_operations_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_asset_id"],
            [
                "source_assets.organization_id",
                "source_assets.workspace_id",
                "source_assets.project_id",
                "source_assets.id",
            ],
            name="fk_source_asset_operations_asset_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "source_asset_id",
                "source_asset_version_id",
            ],
            [
                "source_asset_versions.organization_id",
                "source_asset_versions.workspace_id",
                "source_asset_versions.project_id",
                "source_asset_versions.source_asset_id",
                "source_asset_versions.id",
            ],
            name="fk_source_asset_operations_version_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "operation IN ('create_source_asset', 'create_source_asset_version', "
            "'archive_source_asset')",
            name="ck_source_asset_operation_operation",
        ),
        CheckConstraint(
            "status IN ('reserved', 'accepted')",
            name="ck_source_asset_operation_status",
        ),
        CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_source_asset_operation_digest",
        ),
        CheckConstraint("version >= 1", name="ck_source_asset_operation_version"),
        CheckConstraint(
            "(status = 'reserved' AND source_asset_id IS NULL "
            "AND source_asset_version_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'accepted' AND operation IN ('create_source_asset', "
            "'create_source_asset_version') AND source_asset_id IS NOT NULL "
            "AND source_asset_version_id IS NOT NULL AND completed_at IS NOT NULL) OR "
            "(status = 'accepted' AND operation = 'archive_source_asset' "
            "AND source_asset_id IS NOT NULL AND source_asset_version_id IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_source_asset_operation_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_asset_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    submitted_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_audit_events_workspace_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "action IN ('organization.created', 'workspace.created', 'membership.created', "
            "'project.created', 'project.updated', 'project.activated', 'project.archived', "
            "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
            "'brief.approved', 'brief.archived', 'brief.issue_created', "
            "'brief.issue_resolved', 'brief.issue_dismissed', 'brief.ingestion_accepted', "
            "'brief_ingestion.source_attached', "
            "'source_asset.created', 'source_asset.version_created', "
            "'source_asset.archived')",
            name="ck_audit_action",
        ),
        Index(
            "ix_audit_events_tenant_aggregate",
            "organization_id",
            "workspace_id",
            "aggregate_type",
            "aggregate_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
