"""add an idempotent revision cancellation operation

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_OPERATION_TYPE = (
    "operation IN ('submit_planning_review', 'create_revision_request', "
    "'complete_revision_request', 'create_delivery_package', 'export_delivery_package')"
)
_NEW_OPERATION_TYPE = (
    "operation IN ('submit_planning_review', 'create_revision_request', "
    "'complete_revision_request', 'cancel_revision_request', 'create_delivery_package', "
    "'export_delivery_package')"
)
_OLD_OPERATION_OUTCOME = (
    "(status = 'reserved' AND completed_at IS NULL AND outcome_review_id IS NULL "
    "AND outcome_revision_request_id IS NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(status = 'accepted' AND completed_at IS NOT NULL AND "
    "((operation = 'submit_planning_review' AND outcome_review_id IS NOT NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_export_file_id IS NULL) OR "
    "(operation = 'create_revision_request' AND outcome_review_id IS NOT NULL "
    "AND outcome_revision_request_id IS NOT NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation = 'complete_revision_request' AND outcome_revision_request_id IS NOT NULL "
    "AND outcome_review_id IS NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation = 'create_delivery_package' AND outcome_delivery_package_id IS NOT NULL "
    "AND outcome_delivery_package_version_id IS NOT NULL AND outcome_review_id IS NULL "
    "AND outcome_revision_request_id IS NULL AND outcome_export_file_id IS NULL) OR "
    "(operation = 'export_delivery_package' AND outcome_export_file_id IS NOT NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL)))"
)
_NEW_OPERATION_OUTCOME = _OLD_OPERATION_OUTCOME.replace(
    "(operation = 'complete_revision_request' AND outcome_revision_request_id IS NOT NULL "
    "AND outcome_review_id IS NULL AND outcome_delivery_package_id IS NULL "
    "AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR ",
    "(operation IN ('complete_revision_request', 'cancel_revision_request') "
    "AND outcome_revision_request_id IS NOT NULL AND outcome_review_id IS NULL "
    "AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL "
    "AND outcome_export_file_id IS NULL) OR ",
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
    "'creative_concept.selected', 'script.generated', 'storyboard.generated', "
    "'shot_plan.generated', 'planning_review.submitted', 'planning_revision.requested', "
    "'planning_revision.completed', 'delivery_package.created', 'delivery_package.exported')"
)
_NEW_AUDIT = _OLD_AUDIT[:-1] + ", 'planning_revision.cancelled')"


def upgrade() -> None:
    op.drop_constraint("ck_delivery_operation_type", "delivery_operations", type_="check")
    op.create_check_constraint(
        "ck_delivery_operation_type", "delivery_operations", _NEW_OPERATION_TYPE
    )
    op.drop_constraint("ck_delivery_operation_outcome", "delivery_operations", type_="check")
    op.create_check_constraint(
        "ck_delivery_operation_outcome", "delivery_operations", _NEW_OPERATION_OUTCOME
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)


def downgrade() -> None:
    bind = op.get_bind()
    cancellation_operation_count = int(
        bind.scalar(
            sa.text(
                "SELECT count(*) FROM delivery_operations "
                "WHERE operation = 'cancel_revision_request'"
            )
        )
        or 0
    )
    cancellation_audit_count = int(
        bind.scalar(
            sa.text(
                "SELECT count(*) FROM audit_events WHERE action = 'planning_revision.cancelled'"
            )
        )
        or 0
    )
    if cancellation_operation_count or cancellation_audit_count:
        raise RuntimeError(
            "cannot downgrade revision cancellation support while cancellation rows exist "
            f"(operations={cancellation_operation_count}, audits={cancellation_audit_count}); "
            "manual cleanup is required before downgrading"
        )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
    op.drop_constraint("ck_delivery_operation_outcome", "delivery_operations", type_="check")
    op.create_check_constraint(
        "ck_delivery_operation_outcome", "delivery_operations", _OLD_OPERATION_OUTCOME
    )
    op.drop_constraint("ck_delivery_operation_type", "delivery_operations", type_="check")
    op.create_check_constraint(
        "ck_delivery_operation_type", "delivery_operations", _OLD_OPERATION_TYPE
    )
