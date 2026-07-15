"""create brief ingestion source asset attachments

Revision ID: e8f9a0b1c2d3
Revises: d6e7f8a9b0c1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_AUDIT_ACTIONS = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', "
    "'brief.issue_resolved', 'brief.issue_dismissed', 'brief.ingestion_accepted', "
    "'source_asset.created', 'source_asset.version_created', 'source_asset.archived')"
)
_NEW_AUDIT_ACTIONS = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', "
    "'brief.issue_resolved', 'brief.issue_dismissed', 'brief.ingestion_accepted', "
    "'brief_ingestion.source_attached', 'source_asset.created', "
    "'source_asset.version_created', 'source_asset.archived')"
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_brief_ingestions_tenant_project_id",
        "brief_ingestions",
        ["organization_id", "workspace_id", "project_id", "id"],
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT_ACTIONS)
    op.create_table(
        "brief_ingestion_source_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("brief_ingestion_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=30), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("attached_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "attached_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type IN ('primary_source', 'supporting_source', 'reference')",
            name="ck_brief_ingestion_source_asset_relation_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_brief_ingestion_source_asset_position"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_ingestion_id"],
            [
                "brief_ingestions.organization_id",
                "brief_ingestions.workspace_id",
                "brief_ingestions.project_id",
                "brief_ingestions.id",
            ],
            name="fk_brief_ingestion_source_assets_ingestion_tenant",
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
            name="fk_brief_ingestion_source_assets_asset_tenant",
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
            name="fk_brief_ingestion_source_assets_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_ingestion_id",
            "position",
            name="uq_brief_ingestion_source_assets_position",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_ingestion_id",
            "source_asset_version_id",
            "relation_type",
            name="uq_brief_ingestion_source_assets_version_relation",
        ),
    )
    op.create_index(
        "ix_brief_ingestion_source_assets_ingestion",
        "brief_ingestion_source_assets",
        ["organization_id", "workspace_id", "project_id", "brief_ingestion_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("brief_ingestion_source_assets")
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT_ACTIONS)
    op.drop_constraint("uq_brief_ingestions_tenant_project_id", "brief_ingestions", type_="unique")
