"""Match the intake tenant FK to ORM metadata while preserving all rows."""

from alembic import op

revision = "b6c7d8e9f0a1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_idea_intakes_organization", "idea_intakes", type_="foreignkey")
    op.create_foreign_key(
        "fk_idea_intakes_organization",
        "idea_intakes",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_idea_intakes_organization", "idea_intakes", type_="foreignkey")
    op.create_foreign_key(
        "fk_idea_intakes_organization", "idea_intakes", "organizations", ["organization_id"], ["id"]
    )
