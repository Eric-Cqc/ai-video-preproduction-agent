"""record bounded failures for provider-backed generation reservations

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CREATIVE_STATUS = "status IN ('reserved', 'accepted')"
_NEW_CREATIVE_STATUS = "status IN ('reserved', 'accepted', 'failed')"
_OLD_VISUAL_STATUS = "status IN ('reserved', 'accepted')"
_NEW_VISUAL_STATUS = "status IN ('reserved', 'accepted', 'failed')"

_OLD_CREATIVE_OUTCOME = (
    "(status='reserved' AND completed_at IS NULL AND outcome_concept_run_id IS NULL "
    "AND outcome_candidate_id IS NULL AND outcome_selection_id IS NULL "
    "AND outcome_script_run_id IS NULL AND outcome_script_version_id IS NULL) OR "
    "(status='accepted' AND completed_at IS NOT NULL AND ((operation="
    "'generate_creative_concepts' AND outcome_concept_run_id IS NOT NULL) OR "
    "(operation='select_creative_concept' AND outcome_selection_id IS NOT NULL "
    "AND outcome_candidate_id IS NOT NULL) OR (operation='generate_script' "
    "AND outcome_script_run_id IS NOT NULL AND outcome_script_version_id IS NOT NULL)))"
)
_NEW_CREATIVE_OUTCOME = (
    "(status='reserved' AND completed_at IS NULL AND failure_code IS NULL "
    "AND outcome_concept_run_id IS NULL AND outcome_candidate_id IS NULL "
    "AND outcome_selection_id IS NULL AND outcome_script_run_id IS NULL "
    "AND outcome_script_version_id IS NULL) OR "
    "(status='accepted' AND completed_at IS NOT NULL AND failure_code IS NULL AND ((operation="
    "'generate_creative_concepts' AND outcome_concept_run_id IS NOT NULL) OR "
    "(operation='select_creative_concept' AND outcome_selection_id IS NOT NULL "
    "AND outcome_candidate_id IS NOT NULL) OR (operation='generate_script' "
    "AND outcome_script_run_id IS NOT NULL AND outcome_script_version_id IS NOT NULL))) OR "
    "(status='failed' AND completed_at IS NOT NULL AND failure_code IS NOT NULL "
    "AND outcome_concept_run_id IS NULL AND outcome_candidate_id IS NULL "
    "AND outcome_selection_id IS NULL AND outcome_script_run_id IS NULL "
    "AND outcome_script_version_id IS NULL)"
)

_OLD_VISUAL_OUTCOME = (
    "(status='reserved' AND completed_at IS NULL AND outcome_storyboard_run_id IS NULL "
    "AND outcome_storyboard_version_id IS NULL AND outcome_shot_plan_run_id IS NULL "
    "AND outcome_shot_plan_version_id IS NULL) OR (status='accepted' "
    "AND completed_at IS NOT NULL "
    "AND ((operation='generate_storyboard' AND outcome_storyboard_run_id IS NOT NULL "
    "AND outcome_storyboard_version_id IS NOT NULL AND outcome_shot_plan_run_id IS NULL "
    "AND outcome_shot_plan_version_id IS NULL) OR (operation='generate_shot_plan' "
    "AND outcome_storyboard_run_id IS NULL AND outcome_storyboard_version_id IS NULL "
    "AND outcome_shot_plan_run_id IS NOT NULL "
    "AND outcome_shot_plan_version_id IS NOT NULL)))"
)
_NEW_VISUAL_OUTCOME = (
    "(status='reserved' AND completed_at IS NULL AND failure_code IS NULL "
    "AND outcome_storyboard_run_id IS NULL AND outcome_storyboard_version_id IS NULL "
    "AND outcome_shot_plan_run_id IS NULL AND outcome_shot_plan_version_id IS NULL) OR "
    "(status='accepted' AND completed_at IS NOT NULL AND failure_code IS NULL "
    "AND ((operation='generate_storyboard' AND outcome_storyboard_run_id IS NOT NULL "
    "AND outcome_storyboard_version_id IS NOT NULL AND outcome_shot_plan_run_id IS NULL "
    "AND outcome_shot_plan_version_id IS NULL) OR (operation='generate_shot_plan' "
    "AND outcome_storyboard_run_id IS NULL AND outcome_storyboard_version_id IS NULL "
    "AND outcome_shot_plan_run_id IS NOT NULL "
    "AND outcome_shot_plan_version_id IS NOT NULL))) OR "
    "(status='failed' AND completed_at IS NOT NULL AND failure_code IS NOT NULL "
    "AND outcome_storyboard_run_id IS NULL AND outcome_storyboard_version_id IS NULL "
    "AND outcome_shot_plan_run_id IS NULL AND outcome_shot_plan_version_id IS NULL)"
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
    "'planning_revision.completed', 'planning_revision.cancelled', 'delivery_package.created', "
    "'delivery_package.exported')"
)
_NEW_AUDIT = _OLD_AUDIT.replace(
    "'creative_concept.selected', 'script.generated', 'storyboard.generated', "
    "'shot_plan.generated',",
    "'creative_concept.selected', 'script.generated', 'creative_concept.failed', "
    "'script.failed', 'storyboard.generated', 'storyboard.failed', 'shot_plan.generated', "
    "'shot_plan.failed',",
)


def _replace_constraints(
    *, creative_status: str, creative_outcome: str, visual_status: str, visual_outcome: str
) -> None:
    op.drop_constraint(
        "ck_creative_operation_status", "creative_generation_operations", type_="check"
    )
    op.create_check_constraint(
        "ck_creative_operation_status", "creative_generation_operations", creative_status
    )
    op.drop_constraint(
        "ck_creative_operation_outcome", "creative_generation_operations", type_="check"
    )
    op.create_check_constraint(
        "ck_creative_operation_outcome", "creative_generation_operations", creative_outcome
    )
    op.drop_constraint("ck_visual_operation_status", "visual_planning_operations", type_="check")
    op.create_check_constraint(
        "ck_visual_operation_status", "visual_planning_operations", visual_status
    )
    op.drop_constraint("ck_visual_operation_outcome", "visual_planning_operations", type_="check")
    op.create_check_constraint(
        "ck_visual_operation_outcome", "visual_planning_operations", visual_outcome
    )


def upgrade() -> None:
    op.add_column(
        "creative_generation_operations",
        sa.Column("failure_code", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "visual_planning_operations", sa.Column("failure_code", sa.String(length=40), nullable=True)
    )
    _replace_constraints(
        creative_status=_NEW_CREATIVE_STATUS,
        creative_outcome=_NEW_CREATIVE_OUTCOME,
        visual_status=_NEW_VISUAL_STATUS,
        visual_outcome=_NEW_VISUAL_OUTCOME,
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)


def downgrade() -> None:
    bind = op.get_bind()
    failed_creative = int(
        bind.scalar(
            sa.text("SELECT count(*) FROM creative_generation_operations WHERE status = 'failed'")
        )
        or 0
    )
    failed_visual = int(
        bind.scalar(
            sa.text("SELECT count(*) FROM visual_planning_operations WHERE status = 'failed'")
        )
        or 0
    )
    failed_audits = int(
        bind.scalar(
            sa.text(
                "SELECT count(*) FROM audit_events WHERE action IN "
                "('creative_concept.failed', 'script.failed', "
                "'storyboard.failed', 'shot_plan.failed')"
            )
        )
        or 0
    )
    if failed_creative or failed_visual or failed_audits:
        raise RuntimeError(
            "cannot downgrade failed generation support while failed rows or audits exist "
            f"(creative={failed_creative}, visual={failed_visual}, audits={failed_audits})"
        )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
    _replace_constraints(
        creative_status=_OLD_CREATIVE_STATUS,
        creative_outcome=_OLD_CREATIVE_OUTCOME,
        visual_status=_OLD_VISUAL_STATUS,
        visual_outcome=_OLD_VISUAL_OUTCOME,
    )
    op.drop_column("visual_planning_operations", "failure_code")
    op.drop_column("creative_generation_operations", "failure_code")
