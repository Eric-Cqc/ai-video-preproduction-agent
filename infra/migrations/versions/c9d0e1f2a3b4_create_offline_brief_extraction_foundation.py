"""create offline Brief extraction foundation

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_AUDIT = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
    "'brief.issue_dismissed', 'brief.ingestion_accepted', "
    "'brief_ingestion.source_attached', 'source_asset.created', "
    "'source_asset.version_created', 'source_asset.archived', 'source_object.uploaded', "
    "'document_extraction.completed')"
)
_NEW_AUDIT = _OLD_AUDIT[:-1] + ", 'brief_extraction.completed')"


def upgrade() -> None:
    op.create_table(
        "brief_extraction_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_extraction_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(60), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("prompt_template_id", sa.String(80), nullable=False),
        sa.Column("prompt_template_version", sa.String(20), nullable=False),
        sa.Column("input_extraction_checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("candidate_structured_brief", postgresql.JSONB(), nullable=True),
        sa.Column("candidate_digest", sa.String(64), nullable=True),
        sa.Column("candidate_issues", postgresql.JSONB(), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_brief_extraction_runs_tenant_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "document_extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.project_id",
                "document_extractions.id",
            ],
            name="fk_brief_extraction_runs_document_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('human_review_required', 'failed')",
            name="ck_brief_extraction_run_status",
        ),
        sa.CheckConstraint(
            "input_extraction_checksum ~ '^[0-9a-f]{64}$' AND "
            "(candidate_digest IS NULL OR candidate_digest ~ '^[0-9a-f]{64}$')",
            name="ck_brief_extraction_run_digests",
        ),
        sa.CheckConstraint(
            "(status='human_review_required' AND candidate_structured_brief IS NOT NULL "
            "AND candidate_digest IS NOT NULL) OR "
            "(status='failed' AND candidate_structured_brief IS NULL "
            "AND candidate_digest IS NULL)",
            name="ck_brief_extraction_run_candidate_outcome",
        ),
    )
    op.create_index(
        "ix_brief_extraction_runs_tenant_document",
        "brief_extraction_runs",
        ["organization_id", "workspace_id", "project_id", "document_extraction_id", "created_at"],
    )
    op.create_table(
        "brief_extraction_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("input_character_count", sa.Integer(), nullable=False),
        sa.Column("output_character_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "run_id",
            "attempt_number",
            name="uq_brief_extraction_attempt_number",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "run_id"],
            [
                "brief_extraction_runs.organization_id",
                "brief_extraction_runs.workspace_id",
                "brief_extraction_runs.project_id",
                "brief_extraction_runs.id",
            ],
            name="fk_brief_extraction_attempts_run_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("attempt_number >= 1", name="ck_brief_extraction_attempt_number"),
        sa.CheckConstraint(
            "status IN ('succeeded', 'malformed_output', 'schema_invalid', 'refused', "
            "'timeout', 'provider_error')",
            name="ck_brief_extraction_attempt_status",
        ),
        sa.CheckConstraint(
            "(output_digest IS NULL OR output_digest ~ '^[0-9a-f]{64}$')",
            name="ck_brief_extraction_attempt_output_digest",
        ),
        sa.CheckConstraint(
            "input_character_count >= 0 AND input_character_count <= 128000 AND "
            "output_character_count >= 0",
            name="ck_brief_extraction_attempt_character_counts",
        ),
        sa.CheckConstraint(
            "(status='succeeded' AND error_code IS NULL AND output_digest IS NOT NULL) OR "
            "(status<>'succeeded' AND error_code IS NOT NULL)",
            name="ck_brief_extraction_attempt_outcome",
        ),
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)


def downgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
    op.drop_table("brief_extraction_attempts")
    op.drop_index("ix_brief_extraction_runs_tenant_document", table_name="brief_extraction_runs")
    op.drop_table("brief_extraction_runs")
