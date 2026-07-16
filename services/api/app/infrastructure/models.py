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


class SourceObjectRecord(Base):
    __tablename__ = "source_objects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_source_objects_tenant_project_id",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
            name="uq_source_objects_source_version",
        ),
        UniqueConstraint("storage_adapter", "storage_key", name="uq_source_objects_storage_key"),
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
            name="fk_source_objects_version_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("state = 'available'", name="ck_source_object_state"),
        CheckConstraint(
            "observed_byte_size > 0 AND observed_byte_size <= 104857600",
            name="ck_source_object_byte_size",
        ),
        CheckConstraint(
            "observed_checksum_algorithm = 'sha256'", name="ck_source_object_checksum_algorithm"
        ),
        CheckConstraint(
            "observed_checksum_value ~ '^[0-9a-f]{64}$'", name="ck_source_object_checksum_value"
        ),
        CheckConstraint("version >= 1", name="ck_source_object_version"),
        Index(
            "ix_source_objects_tenant_version",
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    storage_adapter: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_checksum_algorithm: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_checksum_value: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class SourceObjectUploadRecord(Base):
    __tablename__ = "source_object_uploads"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_source_object_uploads_idempotency",
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
            name="fk_source_object_uploads_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_object_id"],
            [
                "source_objects.organization_id",
                "source_objects.workspace_id",
                "source_objects.project_id",
                "source_objects.id",
            ],
            name="fk_source_object_uploads_object_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "operation = 'upload_source_object'", name="ck_source_object_upload_operation"
        ),
        CheckConstraint(
            "status IN ('reserved', 'accepted')", name="ck_source_object_upload_status"
        ),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="ck_source_object_upload_digest"),
        CheckConstraint("version >= 1", name="ck_source_object_upload_version"),
        CheckConstraint(
            "(status = 'reserved' AND source_object_id IS NULL "
            "AND completed_at IS NULL) OR (status = 'accepted' "
            "AND source_object_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_source_object_upload_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_object_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class SourceObjectCleanupRequirementRecord(Base):
    __tablename__ = "source_object_cleanup_requirements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_source_object_cleanup_project_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "storage_adapter", "storage_key", name="uq_source_object_cleanup_storage_key"
        ),
        CheckConstraint(
            "reason_code IN ('database_failure', 'replay_cleanup_failure', "
            "'staging_cleanup_failure')",
            name="ck_source_object_cleanup_reason",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    storage_adapter: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentExtractionRecord(Base):
    __tablename__ = "document_extractions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_document_extractions_tenant_project_id",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
            "parser_id",
            "parser_version",
            "options_digest",
            name="uq_document_extractions_parser_result",
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
            name="fk_document_extractions_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_object_id"],
            [
                "source_objects.organization_id",
                "source_objects.workspace_id",
                "source_objects.project_id",
                "source_objects.id",
            ],
            name="fk_document_extractions_object_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status = 'completed'", name="ck_document_extraction_status"),
        CheckConstraint(
            "source_checksum_algorithm = 'sha256'",
            name="ck_document_extraction_source_checksum_algorithm",
        ),
        CheckConstraint(
            "source_checksum_value ~ '^[0-9a-f]{64}$' "
            "AND options_digest ~ '^[0-9a-f]{64}$' "
            "AND extraction_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_document_extraction_digests",
        ),
        CheckConstraint(
            "character_count >= 0 AND character_count <= 1048576",
            name="ck_document_extraction_character_count",
        ),
        CheckConstraint("warning_count >= 0", name="ck_document_extraction_warning_count"),
        CheckConstraint("truncated = false", name="ck_document_extraction_not_truncated"),
        CheckConstraint("schema_version = '1.0.0'", name="ck_document_extraction_schema_version"),
        Index(
            "ix_document_extractions_tenant_source_version",
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    parser_id: Mapped[str] = mapped_column(String(60), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(20), nullable=False)
    source_checksum_algorithm: Mapped[str] = mapped_column(String(20), nullable=False)
    source_checksum_value: Mapped[str] = mapped_column(String(64), nullable=False)
    options_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    extracted_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    truncated: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)


class DocumentExtractionOperationRecord(Base):
    __tablename__ = "document_extraction_operations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "idempotency_key",
            name="uq_document_extraction_operations_idempotency",
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
            name="fk_document_extraction_operations_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.project_id",
                "document_extractions.id",
            ],
            name="fk_document_extraction_operations_result_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'", name="ck_document_extraction_operation_digest"
        ),
        CheckConstraint(
            "status IN ('reserved', 'accepted')", name="ck_document_extraction_operation_status"
        ),
        CheckConstraint("version >= 1", name="ck_document_extraction_operation_version"),
        CheckConstraint(
            "(status='reserved' AND extraction_id IS NULL "
            "AND completed_at IS NULL) OR (status='accepted' "
            "AND extraction_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_document_extraction_operation_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_asset_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    extraction_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    submitted_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class BriefExtractionRunRecord(Base):
    __tablename__ = "brief_extraction_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_brief_extraction_runs_tenant_project_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "document_extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.project_id",
                "document_extractions.id",
            ],
            name="fk_brief_extraction_runs_document_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('human_review_required', 'failed')",
            name="ck_brief_extraction_run_status",
        ),
        CheckConstraint(
            "input_extraction_checksum ~ '^[0-9a-f]{64}$' AND "
            "(candidate_digest IS NULL OR candidate_digest ~ '^[0-9a-f]{64}$')",
            name="ck_brief_extraction_run_digests",
        ),
        CheckConstraint(
            "(status='human_review_required' AND candidate_structured_brief IS NOT NULL "
            "AND candidate_digest IS NOT NULL) OR "
            "(status='failed' AND candidate_structured_brief IS NULL "
            "AND candidate_digest IS NULL)",
            name="ck_brief_extraction_run_candidate_outcome",
        ),
        Index(
            "ix_brief_extraction_runs_tenant_document",
            "organization_id",
            "workspace_id",
            "project_id",
            "document_extraction_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    document_extraction_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    provider_id: Mapped[str] = mapped_column(String(60), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template_id: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_extraction_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    candidate_structured_brief: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    candidate_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_issues: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BriefExtractionAttemptRecord(Base):
    __tablename__ = "brief_extraction_attempts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "run_id",
            "attempt_number",
            name="uq_brief_extraction_attempt_number",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "run_id"],
            [
                "brief_extraction_runs.organization_id",
                "brief_extraction_runs.workspace_id",
                "brief_extraction_runs.project_id",
                "brief_extraction_runs.id",
            ],
            name="fk_brief_extraction_attempts_run_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("attempt_number >= 1", name="ck_brief_extraction_attempt_number"),
        CheckConstraint(
            "status IN ('succeeded', 'malformed_output', 'schema_invalid', 'refused', "
            "'timeout', 'provider_error')",
            name="ck_brief_extraction_attempt_status",
        ),
        CheckConstraint(
            "(output_digest IS NULL OR output_digest ~ '^[0-9a-f]{64}$')",
            name="ck_brief_extraction_attempt_output_digest",
        ),
        CheckConstraint(
            "input_character_count >= 0 AND input_character_count <= 128000 AND "
            "output_character_count >= 0",
            name="ck_brief_extraction_attempt_character_counts",
        ),
        CheckConstraint(
            "(status='succeeded' AND error_code IS NULL AND output_digest IS NOT NULL) OR "
            "(status<>'succeeded' AND error_code IS NOT NULL)",
            name="ck_brief_extraction_attempt_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    output_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    output_character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BriefCandidateReviewRecord(Base):
    __tablename__ = "brief_candidate_reviews"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_extraction_run_id",
            name="uq_brief_candidate_review_run",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "action",
            "idempotency_key",
            name="uq_brief_candidate_review_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_extraction_run_id"],
            [
                "brief_extraction_runs.organization_id",
                "brief_extraction_runs.workspace_id",
                "brief_extraction_runs.project_id",
                "brief_extraction_runs.id",
            ],
            name="fk_brief_candidate_review_run_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id"],
            [
                "briefs.organization_id",
                "briefs.workspace_id",
                "briefs.project_id",
                "briefs.id",
            ],
            name="fk_brief_candidate_review_brief_tenant",
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
            name="fk_brief_candidate_review_version_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("action IN ('accept', 'reject')", name="ck_brief_candidate_review_action"),
        CheckConstraint(
            "status IN ('reserved', 'accepted', 'rejected')",
            name="ck_brief_candidate_review_status",
        ),
        CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$' AND candidate_digest ~ '^[0-9a-f]{64}$' "
            "AND (accepted_content_digest IS NULL OR accepted_content_digest ~ '^[0-9a-f]{64}$')",
            name="ck_brief_candidate_review_digests",
        ),
        CheckConstraint(
            "(status='reserved' AND completed_at IS NULL AND brief_id IS NULL "
            "AND brief_version_id IS NULL AND rejection_reason IS NULL) OR "
            "(status='accepted' AND action='accept' AND completed_at IS NOT NULL "
            "AND brief_id IS NOT NULL AND brief_version_id IS NOT NULL "
            "AND accepted_content_digest IS NOT NULL AND accepted_content_modified IS NOT NULL "
            "AND rejection_reason IS NULL) OR "
            "(status='rejected' AND action='reject' AND completed_at IS NOT NULL "
            "AND brief_id IS NULL AND brief_version_id IS NULL "
            "AND accepted_content_digest IS NULL AND accepted_content_modified IS NULL "
            "AND rejection_reason IS NOT NULL)",
            name="ck_brief_candidate_review_outcome",
        ),
        CheckConstraint("version >= 1", name="ck_brief_candidate_review_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_extraction_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_content_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted_content_modified: Mapped[bool | None] = mapped_column(nullable=True)
    brief_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    brief_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class CreativeConceptRunRecord(Base):
    __tablename__ = "creative_concept_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "workspace_id", "project_id", "id", name="uq_concept_runs_tenant_id"
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
            name="fk_concept_runs_brief_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('completed', 'failed')", name="ck_concept_run_status"),
        CheckConstraint(
            "failure_category IN ('refusal', 'timeout', 'provider_error', "
            "'malformed_output', 'schema_invalid') OR failure_category IS NULL",
            name="ck_concept_run_failure",
        ),
        CheckConstraint("candidate_count = 3", name="ck_concept_run_candidate_count"),
        CheckConstraint("brief_content_digest ~ '^[0-9a-f]{64}$'", name="ck_concept_run_digest"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    instruction_template_version: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class CreativeConceptCandidateRecord(Base):
    __tablename__ = "creative_concept_candidates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_concept_candidates_tenant_plain_id",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "concept_run_id",
            "id",
            name="uq_concept_candidates_tenant_id",
        ),
        UniqueConstraint("concept_run_id", "candidate_index", name="uq_concept_candidates_index"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "concept_run_id"],
            [
                "creative_concept_runs.organization_id",
                "creative_concept_runs.workspace_id",
                "creative_concept_runs.project_id",
                "creative_concept_runs.id",
            ],
            name="fk_concept_candidates_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("candidate_index BETWEEN 1 AND 3", name="ck_concept_candidate_index"),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="ck_concept_candidate_digest"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreativeConceptSelectionRecord(Base):
    __tablename__ = "creative_concept_selections"
    __table_args__ = (
        UniqueConstraint("concept_run_id", name="uq_concept_selection_run"),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "concept_run_id",
            "concept_candidate_id",
            "id",
            name="uq_concept_selection_lineage",
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_concept_selection_tenant_id",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "concept_run_id",
                "concept_candidate_id",
            ],
            [
                "creative_concept_candidates.organization_id",
                "creative_concept_candidates.workspace_id",
                "creative_concept_candidates.project_id",
                "creative_concept_candidates.concept_run_id",
                "creative_concept_candidates.id",
            ],
            name="fk_concept_selection_candidate",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version >= 1", name="ck_concept_selection_version"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    selected_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ScriptRunRecord(Base):
    __tablename__ = "script_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "workspace_id", "project_id", "id", name="uq_script_runs_tenant_id"
        ),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            "brief_id",
            "brief_version_id",
            "concept_run_id",
            "concept_candidate_id",
            "concept_selection_id",
            name="uq_script_runs_lineage",
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
            name="fk_script_runs_brief_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "concept_run_id",
                "concept_candidate_id",
            ],
            [
                "creative_concept_candidates.organization_id",
                "creative_concept_candidates.workspace_id",
                "creative_concept_candidates.project_id",
                "creative_concept_candidates.concept_run_id",
                "creative_concept_candidates.id",
            ],
            name="fk_script_runs_candidate",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "concept_run_id",
                "concept_candidate_id",
                "concept_selection_id",
            ],
            [
                "creative_concept_selections.organization_id",
                "creative_concept_selections.workspace_id",
                "creative_concept_selections.project_id",
                "creative_concept_selections.concept_run_id",
                "creative_concept_selections.concept_candidate_id",
                "creative_concept_selections.id",
            ],
            name="fk_script_runs_selection",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('completed', 'failed')", name="ck_script_run_status"),
        CheckConstraint(
            "brief_content_digest ~ '^[0-9a-f]{64}$' AND concept_content_digest ~ '^[0-9a-f]{64}$'",
            name="ck_script_run_digests",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_selection_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    concept_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    instruction_template_version: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ScriptVersionRecord(Base):
    __tablename__ = "script_versions"
    __table_args__ = (
        UniqueConstraint("script_run_id", "version_number", name="uq_script_versions_number"),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_script_versions_tenant_id",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "script_run_id",
                "brief_id",
                "brief_version_id",
                "concept_run_id",
                "concept_candidate_id",
                "concept_selection_id",
            ],
            [
                "script_runs.organization_id",
                "script_runs.workspace_id",
                "script_runs.project_id",
                "script_runs.id",
                "script_runs.brief_id",
                "script_runs.brief_version_id",
                "script_runs.concept_run_id",
                "script_runs.concept_candidate_id",
                "script_runs.concept_selection_id",
            ],
            name="fk_script_versions_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number = 1", name="ck_script_version_number"),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="ck_script_version_digest"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    script_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    brief_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_candidate_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    concept_selection_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreativeGenerationOperationRecord(Base):
    __tablename__ = "creative_generation_operations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_creative_generation_operation_key",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_creative_operation_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "outcome_concept_run_id"],
            [
                "creative_concept_runs.organization_id",
                "creative_concept_runs.workspace_id",
                "creative_concept_runs.project_id",
                "creative_concept_runs.id",
            ],
            name="fk_creative_operation_concept_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "outcome_candidate_id"],
            [
                "creative_concept_candidates.organization_id",
                "creative_concept_candidates.workspace_id",
                "creative_concept_candidates.project_id",
                "creative_concept_candidates.id",
            ],
            name="fk_creative_operation_candidate",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "outcome_selection_id"],
            [
                "creative_concept_selections.organization_id",
                "creative_concept_selections.workspace_id",
                "creative_concept_selections.project_id",
                "creative_concept_selections.id",
            ],
            name="fk_creative_operation_selection",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "outcome_script_run_id"],
            [
                "script_runs.organization_id",
                "script_runs.workspace_id",
                "script_runs.project_id",
                "script_runs.id",
            ],
            name="fk_creative_operation_script_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "outcome_script_version_id"],
            [
                "script_versions.organization_id",
                "script_versions.workspace_id",
                "script_versions.project_id",
                "script_versions.id",
            ],
            name="fk_creative_operation_script_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "operation IN ('generate_creative_concepts', 'select_creative_concept', "
            "'generate_script')",
            name="ck_creative_operation_type",
        ),
        CheckConstraint("status IN ('reserved', 'accepted')", name="ck_creative_operation_status"),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="ck_creative_operation_digest"),
        CheckConstraint(
            "(status='reserved' AND completed_at IS NULL AND outcome_concept_run_id IS NULL "
            "AND outcome_candidate_id IS NULL AND outcome_selection_id IS NULL "
            "AND outcome_script_run_id IS NULL AND outcome_script_version_id IS NULL) OR "
            "(status='accepted' AND completed_at IS NOT NULL AND ((operation="
            "'generate_creative_concepts' AND outcome_concept_run_id IS NOT NULL) OR "
            "(operation='select_creative_concept' AND outcome_selection_id IS NOT NULL "
            "AND outcome_candidate_id IS NOT NULL) OR (operation='generate_script' "
            "AND outcome_script_run_id IS NOT NULL AND outcome_script_version_id IS NOT NULL)))",
            name="ck_creative_operation_outcome",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    outcome_concept_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    outcome_candidate_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    outcome_selection_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    outcome_script_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    outcome_script_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_by_actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


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
            "'source_asset.archived', 'source_object.uploaded', "
            "'document_extraction.completed', 'brief_extraction.completed', "
            "'brief_candidate.accepted', 'brief_candidate.rejected', "
            "'creative_concept.generated', 'creative_concept.selected', 'script.generated')",
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
