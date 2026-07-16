"""create Brief candidate reviews

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
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
    "'document_extraction.completed', 'brief_extraction.completed')"
)
_NEW_AUDIT = _OLD_AUDIT[:-1] + ", 'brief_candidate.accepted', 'brief_candidate.rejected')"


def upgrade() -> None:
    op.create_table(
        "brief_candidate_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("brief_extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("candidate_digest", sa.String(64), nullable=False),
        sa.Column("accepted_content_digest", sa.String(64), nullable=True),
        sa.Column("accepted_content_modified", sa.Boolean(), nullable=True),
        sa.Column("brief_id", sa.Uuid(), nullable=True),
        sa.Column("brief_version_id", sa.Uuid(), nullable=True),
        sa.Column("rejection_reason", sa.String(20), nullable=True),
        sa.Column("rejection_note", sa.String(500), nullable=True),
        sa.Column("submitted_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "brief_extraction_run_id",
            name="uq_brief_candidate_review_run",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "action",
            "idempotency_key",
            name="uq_brief_candidate_review_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_extraction_run_id"],
            [
                "brief_extraction_runs.organization_id",
                "brief_extraction_runs.workspace_id",
                "brief_extraction_runs.project_id",
                "brief_extraction_runs.id",
            ],
            name="fk_brief_candidate_review_run_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "brief_id"],
            [
                "briefs.organization_id",
                "briefs.workspace_id",
                "briefs.project_id",
                "briefs.id",
            ],
            name="fk_brief_candidate_review_brief_tenant",
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
            name="fk_brief_candidate_review_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action IN ('accept', 'reject')", name="ck_brief_candidate_review_action"
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted', 'rejected')",
            name="ck_brief_candidate_review_status",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$' AND candidate_digest ~ '^[0-9a-f]{64}$' "
            "AND (accepted_content_digest IS NULL OR accepted_content_digest ~ '^[0-9a-f]{64}$')",
            name="ck_brief_candidate_review_digests",
        ),
        sa.CheckConstraint(
            "(status='reserved' AND completed_at IS NULL AND brief_id IS NULL "
            "AND brief_version_id IS NULL AND rejection_reason IS NULL) OR "
            "(status='accepted' AND action='accept' AND completed_at IS NOT NULL "
            "AND brief_id IS NOT NULL AND brief_version_id IS NOT NULL "
            "AND accepted_content_digest IS NOT NULL AND accepted_content_modified IS NOT NULL "
            "AND rejection_reason IS NULL) OR "
            "(status='rejected' AND action='reject' AND completed_at IS NOT NULL "
            "AND brief_id IS NULL AND brief_version_id IS NULL "
            "AND accepted_content_digest IS NULL AND accepted_content_modified IS NULL "
            "AND rejection_reason IS NOT NULL)",
            name="ck_brief_candidate_review_outcome",
        ),
        sa.CheckConstraint("version >= 1", name="ck_brief_candidate_review_version"),
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)


def downgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
    op.drop_table("brief_candidate_reviews")
