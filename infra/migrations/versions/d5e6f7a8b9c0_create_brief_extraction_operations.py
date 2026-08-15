"""create brief extraction idempotency operations

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brief_extraction_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("document_extraction_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_brief_extraction_operation_key",
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
            name="fk_brief_extraction_operations_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "document_extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.project_id",
                "document_extractions.id",
            ],
            name="fk_brief_extraction_operations_document_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "run_id"],
            [
                "brief_extraction_runs.organization_id",
                "brief_extraction_runs.workspace_id",
                "brief_extraction_runs.project_id",
                "brief_extraction_runs.id",
            ],
            name="fk_brief_extraction_operations_run_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "operation = 'brief_extraction'", name="ck_brief_extraction_operation_type"
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_brief_extraction_operation_digest",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted')",
            name="ck_brief_extraction_operation_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_brief_extraction_operation_version"),
        sa.CheckConstraint(
            "(status='reserved' AND run_id IS NULL AND completed_at IS NULL) OR "
            "(status='accepted' AND run_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_brief_extraction_operation_outcome",
        ),
    )


def downgrade() -> None:
    op.drop_table("brief_extraction_operations")
