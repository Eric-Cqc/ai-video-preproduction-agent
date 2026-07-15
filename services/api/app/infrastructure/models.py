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
            "'project.created', 'project.updated', 'project.activated', 'project.archived')",
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
