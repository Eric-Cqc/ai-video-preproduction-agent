"""create idea intake workflow

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7
Create Date: 2026-07-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_BRIEF_SOURCE_TYPE = "source_type IN ('manual', 'imported_structured')"
_NEW_BRIEF_SOURCE_TYPE = "source_type IN ('manual', 'imported_structured', 'idea_intake')"

_OLD_AUDIT = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
    "'brief.issue_dismissed', 'brief.ingestion_accepted', 'brief_ingestion.source_attached',"
    " 'source_asset.created', 'source_asset.version_created', 'source_asset.archived', "
    "'source_object.uploaded', 'document_extraction.completed', "
    "'brief_extraction.completed', 'brief_candidate.accepted', 'brief_candidate.rejected', "
    "'creative_concept.generated', 'creative_concept.selected', 'script.generated', "
    "'creative_concept.failed', 'script.failed', 'storyboard.generated', "
    "'storyboard.failed', 'shot_plan.generated', 'shot_plan.failed', "
    "'planning_review.submitted', 'planning_revision.requested', "
    "'planning_revision.completed', 'planning_revision.cancelled', "
    "'planning_revision.failed', 'delivery_package.created', 'delivery_package.exported')"
)
_NEW_AUDIT = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
    "'brief.issue_dismissed', 'brief.ingestion_accepted', 'idea_intake.structured', "
    "'idea_intake.updated', 'idea_intake.confirmed', 'brief_ingestion.source_attached', "
    "'source_asset.created', 'source_asset.version_created', 'source_asset.archived', "
    "'source_object.uploaded', 'document_extraction.completed', "
    "'brief_extraction.completed', 'brief_candidate.accepted', 'brief_candidate.rejected', "
    "'creative_concept.generated', 'creative_concept.selected', 'script.generated', "
    "'creative_concept.failed', 'script.failed', 'storyboard.generated', "
    "'storyboard.failed', 'shot_plan.generated', 'shot_plan.failed', "
    "'planning_review.submitted', 'planning_revision.requested', "
    "'planning_revision.completed', 'planning_revision.cancelled', "
    "'planning_revision.failed', 'delivery_package.created', 'delivery_package.exported')"
)


def upgrade() -> None:
    op.drop_constraint("ck_brief_version_source_type", "brief_versions", type_="check")
    op.create_check_constraint(
        "ck_brief_version_source_type", "brief_versions", _NEW_BRIEF_SOURCE_TYPE
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)

    op.create_table(
        "idea_intakes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("raw_idea", sa.Text(), nullable=False),
        sa.Column("objective", sa.String(length=500), nullable=True),
        sa.Column("platform", sa.String(length=120), nullable=True),
        sa.Column("audience", sa.String(length=500), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("tone", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("key_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("call_to_action", sa.String(length=500), nullable=True),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("must_include", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("must_avoid", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=True),
        sa.Column("brief_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("length(btrim(raw_idea)) > 0", name="ck_idea_intake_raw_idea"),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds BETWEEN 1 AND 3600",
            name="ck_idea_intake_duration",
        ),
        sa.CheckConstraint("status IN ('structured', 'confirmed')", name="ck_idea_intake_status"),
        sa.CheckConstraint(
            "jsonb_typeof(tone) = 'array' AND jsonb_array_length(tone) <= 10 AND "
            "jsonb_typeof(key_messages) = 'array' AND jsonb_array_length(key_messages) <= 20 AND "
            "jsonb_typeof(constraints) = 'array' AND jsonb_array_length(constraints) <= 20 AND "
            "jsonb_typeof(must_include) = 'array' AND jsonb_array_length(must_include) <= 20 AND "
            "jsonb_typeof(must_avoid) = 'array' AND jsonb_array_length(must_avoid) <= 20 AND "
            "jsonb_typeof(assumptions) = 'array' AND jsonb_array_length(assumptions) <= 20 AND "
            "jsonb_typeof(missing_fields) = 'array' AND jsonb_array_length(missing_fields) <= 3",
            name="ck_idea_intake_array_bounds",
        ),
        sa.CheckConstraint(
            "(status = 'structured' AND brief_id IS NULL AND brief_version_id IS NULL) OR "
            "(status = 'confirmed' AND brief_id IS NOT NULL AND brief_version_id IS NOT NULL)",
            name="ck_idea_intake_confirmation",
        ),
        sa.CheckConstraint("version >= 1", name="ck_idea_intake_version"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_idea_intakes_organization"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_idea_intakes_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id"],
            ["briefs.organization_id", "briefs.workspace_id", "briefs.project_id", "briefs.id"],
            name="fk_idea_intakes_brief_tenant",
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
            name="fk_idea_intakes_brief_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_idea_intakes_tenant_project_id",
        ),
    )
    op.create_index(
        "ix_idea_intakes_tenant_project",
        "idea_intakes",
        ["organization_id", "workspace_id", "project_id", "created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM idea_intakes")):
        raise RuntimeError("Refusing downgrade: Idea Intake data exists")
    op.drop_index("ix_idea_intakes_tenant_project", table_name="idea_intakes")
    op.drop_table("idea_intakes")

    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
    op.drop_constraint("ck_brief_version_source_type", "brief_versions", type_="check")
    op.create_check_constraint(
        "ck_brief_version_source_type", "brief_versions", _OLD_BRIEF_SOURCE_TYPE
    )
