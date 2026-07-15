"""create controlled brief ingestions

Revision ID: b2a7c9d1e4f0
Revises: 8d4e2a1f7c90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2a7c9d1e4f0"
down_revision: str | None = "8d4e2a1f7c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_action",
        "audit_events",
        "action IN ('organization.created', 'workspace.created', 'membership.created', "
        "'project.created', 'project.updated', 'project.activated', 'project.archived', "
        "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
        "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
        "'brief.issue_dismissed', 'brief.ingestion_accepted')",
    )
    op.create_table(
        "brief_ingestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=True),
        sa.Column("brief_version_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_reference", sa.String(200), nullable=True),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rejection_code", sa.String(50), nullable=True),
        sa.Column("rejection_details", sa.String(200), nullable=True),
        sa.Column("submitted_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "operation IN ('create_brief', 'create_version')", name="ck_brief_ingestion_operation"
        ),
        sa.CheckConstraint(
            "source_type IN ('imported_structured', 'api_structured')",
            name="ck_brief_ingestion_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted', 'rejected')", name="ck_brief_ingestion_status"
        ),
        sa.CheckConstraint("payload_digest ~ '^[0-9a-f]{64}$'", name="ck_brief_ingestion_digest"),
        sa.CheckConstraint("schema_version = '1.0.0'", name="ck_brief_ingestion_schema_version"),
        sa.CheckConstraint("version >= 1", name="ck_brief_ingestion_version"),
        sa.CheckConstraint(
            "(status = 'reserved' AND brief_id IS NULL AND brief_version_id IS NULL "
            "AND completed_at IS NULL AND rejection_code IS NULL AND rejection_details IS NULL) OR "
            "(status = 'accepted' AND brief_id IS NOT NULL AND brief_version_id IS NOT NULL "
            "AND completed_at IS NOT NULL AND rejection_code IS NULL "
            "AND rejection_details IS NULL) OR (status = 'rejected' AND brief_id IS NULL "
            "AND brief_version_id IS NULL)",
            name="ck_brief_ingestion_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_brief_ingestions_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id"],
            ["briefs.organization_id", "briefs.workspace_id", "briefs.project_id", "briefs.id"],
            name="fk_brief_ingestions_brief_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_brief_ingestions_idempotency",
        ),
    )


def downgrade() -> None:
    op.drop_table("brief_ingestions")
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_action",
        "audit_events",
        "action IN ('organization.created', 'workspace.created', 'membership.created', "
        "'project.created', 'project.updated', 'project.activated', 'project.archived', "
        "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
        "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
        "'brief.issue_dismissed')",
    )
