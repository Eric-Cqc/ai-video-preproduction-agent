"""Align intake drafts with canonical Brief duration without rewriting data.

Revision ID: b5c6d7e8f9a0
Revises: b4c5d6e7f8a9
"""

import sqlalchemy as sa
from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    invalid = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM idea_intakes WHERE duration_seconds NOT BETWEEN 15 AND 60")
    )
    if invalid:
        raise RuntimeError(
            "Cannot align duration: existing drafts outside 15–60 seconds require human review"
        )
    op.drop_constraint("ck_idea_intake_duration", "idea_intakes", type_="check")
    op.create_check_constraint(
        "ck_idea_intake_duration",
        "idea_intakes",
        "duration_seconds IS NULL OR duration_seconds BETWEEN 15 AND 60",
    )


def downgrade() -> None:
    op.drop_constraint("ck_idea_intake_duration", "idea_intakes", type_="check")
    op.create_check_constraint(
        "ck_idea_intake_duration",
        "idea_intakes",
        "duration_seconds IS NULL OR duration_seconds BETWEEN 1 AND 3600",
    )
