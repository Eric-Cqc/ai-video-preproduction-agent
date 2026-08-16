"""record failed provider-backed revision completion reservations

Revision ID: a2b3c4d5e6f7
Revises: f0a1b2c3d4e5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATUS = "status IN ('reserved', 'accepted')"
_NEW_STATUS = "status IN ('reserved', 'accepted', 'failed')"
_OLD_OUTCOME = (
    "(status = 'reserved' AND completed_at IS NULL AND outcome_review_id IS NULL "
    "AND outcome_revision_request_id IS NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(status = 'accepted' AND completed_at IS NOT NULL AND ((operation = 'submit_planning_review' "
    "AND outcome_review_id IS NOT NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation = 'create_revision_request' AND outcome_review_id IS NOT NULL "
    "AND outcome_revision_request_id IS NOT NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation IN ('complete_revision_request', 'cancel_revision_request') "
    "AND outcome_revision_request_id IS NOT NULL AND outcome_review_id IS NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_export_file_id IS NULL) OR (operation = 'create_delivery_package' "
    "AND outcome_delivery_package_id IS NOT NULL "
    "AND outcome_delivery_package_version_id IS NOT NULL "
    "AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL "
    "AND outcome_export_file_id IS NULL) OR (operation = 'export_delivery_package' "
    "AND outcome_export_file_id IS NOT NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_review_id IS NULL "
    "AND outcome_revision_request_id IS NULL)))"
)
_NEW_OUTCOME = (
    "(status = 'reserved' AND completed_at IS NULL AND failure_code IS NULL "
    "AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_export_file_id IS NULL) OR (status = 'accepted' AND completed_at IS NOT NULL "
    "AND failure_code IS NULL AND ((operation = 'submit_planning_review' AND outcome_review_id "
    "IS NOT NULL AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id "
    "IS NULL AND outcome_export_file_id IS NULL) OR (operation = 'create_revision_request' "
    "AND outcome_review_id IS NOT NULL AND outcome_revision_request_id IS NOT NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_export_file_id IS NULL) OR (operation IN ('complete_revision_request', "
    "'cancel_revision_request') AND outcome_revision_request_id IS NOT NULL "
    "AND outcome_review_id IS NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation = 'create_delivery_package' AND outcome_delivery_package_id IS NOT NULL "
    "AND outcome_delivery_package_version_id IS NOT NULL AND outcome_review_id IS NULL "
    "AND outcome_revision_request_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation = 'export_delivery_package' AND outcome_export_file_id IS NOT NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL))) OR "
    "(status = 'failed' AND operation = 'complete_revision_request' AND completed_at IS NOT NULL "
    "AND failure_code IS NOT NULL AND outcome_review_id IS NULL AND outcome_revision_request_id "
    "IS NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL)"
)
_OLD_AUDIT = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
    "'brief.issue_dismissed', 'brief.ingestion_accepted', 'brief_ingestion.source_attached', "
    "'source_asset.created', 'source_asset.version_created', 'source_asset.archived', "
    "'source_object.uploaded', 'document_extraction.completed', 'brief_extraction.completed', "
    "'brief_candidate.accepted', 'brief_candidate.rejected', 'creative_concept.generated', "
    "'creative_concept.selected', 'script.generated', 'creative_concept.failed', "
    "'script.failed', 'storyboard.generated', 'storyboard.failed', 'shot_plan.generated', "
    "'shot_plan.failed', 'planning_review.submitted', 'planning_revision.requested', "
    "'planning_revision.completed', 'planning_revision.cancelled', 'delivery_package.created', "
    "'delivery_package.exported')"
)
_NEW_AUDIT = _OLD_AUDIT.replace(
    "'planning_revision.completed', 'planning_revision.cancelled',",
    "'planning_revision.completed', 'planning_revision.cancelled', 'planning_revision.failed',",
)


def _replace_constraints(*, status: str, outcome: str, audit: str) -> None:
    op.drop_constraint("ck_delivery_operation_status", "delivery_operations", type_="check")
    op.create_check_constraint("ck_delivery_operation_status", "delivery_operations", status)
    op.drop_constraint("ck_delivery_operation_outcome", "delivery_operations", type_="check")
    op.create_check_constraint("ck_delivery_operation_outcome", "delivery_operations", outcome)
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", audit)


def upgrade() -> None:
    op.add_column(
        "delivery_operations", sa.Column("failure_code", sa.String(length=40), nullable=True)
    )
    _replace_constraints(status=_NEW_STATUS, outcome=_NEW_OUTCOME, audit=_NEW_AUDIT)


def downgrade() -> None:
    bind = op.get_bind()
    failed_operations = int(
        bind.scalar(sa.text("SELECT count(*) FROM delivery_operations WHERE status = 'failed'"))
        or 0
    )
    failed_audits = int(
        bind.scalar(
            sa.text("SELECT count(*) FROM audit_events WHERE action = 'planning_revision.failed'")
        )
        or 0
    )
    if failed_operations or failed_audits:
        raise RuntimeError(
            "cannot downgrade failed revision completion support while failed rows or audits exist "
            f"(operations={failed_operations}, audits={failed_audits})"
        )
    _replace_constraints(status=_OLD_STATUS, outcome=_OLD_OUTCOME, audit=_OLD_AUDIT)
    op.drop_column("delivery_operations", "failure_code")
