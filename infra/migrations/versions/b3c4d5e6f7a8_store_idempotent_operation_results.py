"""store operation-time results for truthful idempotent replays

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "brief_ingestions",
        sa.Column("result_brief_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "brief_ingestions",
        sa.Column("result_brief_latest_version_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "brief_ingestions",
        sa.Column("result_brief_aggregate_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "brief_ingestions",
        sa.Column("result_brief_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_asset_operations",
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_asset_operations",
        sa.Column("result_asset_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "source_asset_operations",
        sa.Column("result_asset_latest_version_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "source_asset_operations",
        sa.Column("result_asset_aggregate_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "source_asset_operations",
        sa.Column("result_asset_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_source_asset_operation_duplicate_count",
        "source_asset_operations",
        "duplicate_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_asset_operation_duplicate_count",
        "source_asset_operations",
        type_="check",
    )
    op.drop_column("source_asset_operations", "result_asset_updated_at")
    op.drop_column("source_asset_operations", "result_asset_aggregate_version")
    op.drop_column("source_asset_operations", "result_asset_latest_version_number")
    op.drop_column("source_asset_operations", "result_asset_status")
    op.drop_column("source_asset_operations", "duplicate_count")
    op.drop_column("brief_ingestions", "result_brief_updated_at")
    op.drop_column("brief_ingestions", "result_brief_aggregate_version")
    op.drop_column("brief_ingestions", "result_brief_latest_version_number")
    op.drop_column("brief_ingestions", "result_brief_status")
