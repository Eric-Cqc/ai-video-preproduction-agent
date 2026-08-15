"""add nullable provider usage metadata to provider call records

Revision ID: e9f0a1b2c3d4
Revises: d5e6f7a8b9c0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "brief_extraction_runs",
    "creative_concept_runs",
    "script_runs",
    "storyboard_runs",
    "shot_plan_runs",
    "delivery_operations",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("input_tokens", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("output_tokens", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("total_tokens", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("provider_request_id", sa.String(length=200), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "provider_request_id")
        op.drop_column(table, "total_tokens")
        op.drop_column(table, "output_tokens")
        op.drop_column(table, "input_tokens")
