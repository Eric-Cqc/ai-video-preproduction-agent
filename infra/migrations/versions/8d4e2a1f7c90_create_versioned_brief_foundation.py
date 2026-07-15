"""create versioned brief foundation

Revision ID: 8d4e2a1f7c90
Revises: fca964a30853
Create Date: 2026-07-15 18:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8d4e2a1f7c90"
down_revision: str | None = "fca964a30853"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_AUDIT_ACTIONS = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived')"
)
_NEW_AUDIT_ACTIONS = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', "
    "'brief.issue_resolved', 'brief.issue_dismissed')"
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_projects_tenant_id", "projects", ["organization_id", "workspace_id", "id"]
    )

    op.create_table(
        "briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=False),
        sa.Column("latest_version_number", sa.Integer(), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'archived')",
            name="ck_brief_status",
        ),
        sa.CheckConstraint("latest_version_number >= 1", name="ck_brief_latest_version"),
        sa.CheckConstraint("version >= 1", name="ck_brief_version"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_briefs_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_briefs_tenant_project_id",
        ),
    )
    op.create_index(
        "ix_briefs_tenant_project",
        "briefs",
        ["organization_id", "workspace_id", "project_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "brief_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=20), nullable=False),
        sa.Column(
            "structured_content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=True),
        sa.Column("change_summary", sa.String(length=500), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_actor_subject", sa.String(length=200), nullable=True),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.Column("content_schema_version", sa.String(length=20), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="ck_brief_version_number"),
        sa.CheckConstraint(
            "lifecycle_state IN ('draft', 'in_review', 'approved', 'superseded')",
            name="ck_brief_version_lifecycle",
        ),
        sa.CheckConstraint(
            "source_type IN ('manual', 'imported_structured')",
            name="ck_brief_version_source_type",
        ),
        sa.CheckConstraint(
            "content_schema_version = '1.0.0'", name="ck_brief_content_schema_version"
        ),
        sa.CheckConstraint(
            "(approved_at IS NULL) = (approved_by_actor_subject IS NULL)",
            name="ck_brief_version_approval_pair",
        ),
        sa.CheckConstraint(
            "(lifecycle_state = 'draft' AND submitted_for_review_at IS NULL "
            "AND approved_at IS NULL) OR "
            "(lifecycle_state = 'in_review' AND submitted_for_review_at IS NOT NULL "
            "AND approved_at IS NULL) OR "
            "(lifecycle_state = 'approved' AND submitted_for_review_at IS NOT NULL "
            "AND approved_at IS NOT NULL) OR lifecycle_state = 'superseded'",
            name="ck_brief_version_lifecycle_metadata",
        ),
        sa.ForeignKeyConstraint(
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
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brief_id", "version_number", name="uq_brief_versions_number"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_id",
            "id",
            name="uq_brief_versions_tenant_brief_id",
        ),
    )
    op.create_index(
        "ix_brief_versions_tenant_brief",
        "brief_versions",
        ["organization_id", "workspace_id", "project_id", "brief_id", "version_number"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_briefs_current_version",
        "briefs",
        "brief_versions",
        ["organization_id", "workspace_id", "project_id", "id", "current_version_id"],
        ["organization_id", "workspace_id", "project_id", "brief_id", "id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "requirement_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column("brief_version_id", sa.Uuid(), nullable=False),
        sa.Column("issue_type", sa.String(length=30), nullable=False),
        sa.Column("field_path", sa.String(length=300), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolution_note", sa.String(length=1000), nullable=True),
        sa.Column("created_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column("resolved_by_actor_subject", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "issue_type IN ('missing', 'ambiguous', 'conflicting', 'invalid', 'compliance_risk')",
            name="ck_requirement_issue_type",
        ),
        sa.CheckConstraint(
            "severity IN ('blocking', 'warning', 'informational')",
            name="ck_requirement_issue_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_requirement_issue_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_requirement_issue_version"),
        sa.CheckConstraint(
            "(status = 'open' AND resolution_note IS NULL "
            "AND resolved_by_actor_subject IS NULL AND resolved_at IS NULL) OR "
            "(status IN ('resolved', 'dismissed') AND resolution_note IS NOT NULL "
            "AND resolved_by_actor_subject IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_requirement_issue_resolution",
        ),
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_requirement_issues_tenant_version",
        "requirement_issues",
        [
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_id",
            "brief_version_id",
            "status",
        ],
        unique=False,
    )

    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT_ACTIONS)


def downgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT_ACTIONS)

    op.drop_index("ix_requirement_issues_tenant_version", table_name="requirement_issues")
    op.drop_table("requirement_issues")
    op.drop_constraint("fk_briefs_current_version", "briefs", type_="foreignkey")
    op.drop_index("ix_brief_versions_tenant_brief", table_name="brief_versions")
    op.drop_table("brief_versions")
    op.drop_index("ix_briefs_tenant_project", table_name="briefs")
    op.drop_table("briefs")
    op.drop_constraint("uq_projects_tenant_id", "projects", type_="unique")
