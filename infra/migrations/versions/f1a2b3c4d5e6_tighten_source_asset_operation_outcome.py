"""tighten source asset operation accepted outcome

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_OUTCOME = (
    "(status = 'reserved' AND source_asset_id IS NULL "
    "AND source_asset_version_id IS NULL AND completed_at IS NULL) OR "
    "(status = 'accepted' AND operation IN ('create_source_asset', "
    "'create_source_asset_version') AND source_asset_id IS NOT NULL "
    "AND source_asset_version_id IS NOT NULL AND completed_at IS NOT NULL) OR "
    "(status = 'accepted' AND operation = 'archive_source_asset' "
    "AND source_asset_id IS NOT NULL AND completed_at IS NOT NULL)"
)
_NEW_OUTCOME = (
    "(status = 'reserved' AND source_asset_id IS NULL "
    "AND source_asset_version_id IS NULL AND completed_at IS NULL) OR "
    "(status = 'accepted' AND operation IN ('create_source_asset', "
    "'create_source_asset_version', 'archive_source_asset') "
    "AND source_asset_id IS NOT NULL AND source_asset_version_id IS NOT NULL "
    "AND completed_at IS NOT NULL)"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_source_asset_operation_outcome", "source_asset_operations", type_="check"
    )
    op.create_check_constraint(
        "ck_source_asset_operation_outcome", "source_asset_operations", _NEW_OUTCOME
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_asset_operation_outcome", "source_asset_operations", type_="check"
    )
    op.create_check_constraint(
        "ck_source_asset_operation_outcome", "source_asset_operations", _OLD_OUTCOME
    )
