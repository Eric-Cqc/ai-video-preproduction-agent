"""create source asset operations

Revision ID: d6e7f8a9b0c1
Revises: c4f1d2a9b8e7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c4f1d2a9b8e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_AUDIT_ACTIONS = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', "
    "'brief.issue_resolved', 'brief.issue_dismissed', 'brief.ingestion_accepted')"
)
_NEW_AUDIT_ACTIONS = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', "
    "'brief.issue_resolved', 'brief.issue_dismissed', 'brief.ingestion_accepted', "
    "'source_asset.created', 'source_asset.version_created', 'source_asset.archived')"
)


def upgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT_ACTIONS)
    op.create_table(
        "source_asset_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "operation IN ('create_source_asset', 'create_source_asset_version', "
            "'archive_source_asset')",
            name="ck_source_asset_operation_operation",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted')",
            name="ck_source_asset_operation_status",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_source_asset_operation_digest",
        ),
        sa.CheckConstraint("version >= 1", name="ck_source_asset_operation_version"),
        sa.CheckConstraint(
            "(status = 'reserved' AND source_asset_id IS NULL "
            "AND source_asset_version_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'accepted' AND operation IN ('create_source_asset', "
            "'create_source_asset_version') AND source_asset_id IS NOT NULL "
            "AND source_asset_version_id IS NOT NULL AND completed_at IS NOT NULL) OR "
            "(status = 'accepted' AND operation = 'archive_source_asset' "
            "AND source_asset_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_source_asset_operation_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_source_asset_operations_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
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
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_source_asset_operations_idempotency",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_asset_operations")
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT_ACTIONS)
