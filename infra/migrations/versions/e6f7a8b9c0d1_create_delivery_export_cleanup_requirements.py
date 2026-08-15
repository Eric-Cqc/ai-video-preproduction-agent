"""create durable delivery export cleanup requirements

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_export_cleanup_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("storage_adapter", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_delivery_export_cleanup_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "storage_adapter", "storage_key", name="uq_delivery_export_cleanup_storage_key"
        ),
        sa.CheckConstraint(
            "reason_code IN ('export_cleanup_failure')",
            name="ck_delivery_export_cleanup_reason",
        ),
    )


def downgrade() -> None:
    op.drop_table("delivery_export_cleanup_requirements")
