"""create Stage 13 review, revision and delivery workflow."""

# SQL CHECK expressions are kept readable as database predicates.
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "9031dcffc3ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    "'shot_plan.generated')"
)
_NEW_AUDIT = (
    _OLD_AUDIT[:-1] + ", 'planning_review.submitted', 'planning_revision.requested', "
    "'planning_revision.completed', 'delivery_package.created', 'delivery_package.exported')"
)

_SCOPE = ["organization_id", "workspace_id", "project_id"]
_PROJECT_REF = ["projects.organization_id", "projects.workspace_id", "projects.id"]


def _scope_fk(columns: list[str], target: list[str], name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(columns, target, name=name, ondelete="RESTRICT")


def _artifact_fk(table: str, column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        _SCOPE + [column],
        [f"{table}.organization_id", f"{table}.workspace_id", f"{table}.project_id", f"{table}.id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.drop_constraint("ck_script_version_number", "script_versions", type_="check")
    op.create_check_constraint("ck_script_version_number", "script_versions", "version_number >= 1")
    op.drop_constraint("ck_storyboard_version_bounds", "storyboard_versions", type_="check")
    op.create_check_constraint(
        "ck_storyboard_version_bounds",
        "storyboard_versions",
        "version_number >= 1 AND total_duration_seconds > 0 AND scene_count BETWEEN 1 AND 60",
    )
    op.drop_constraint("ck_shot_plan_version_bounds", "shot_plan_versions", type_="check")
    op.create_check_constraint(
        "ck_shot_plan_version_bounds",
        "shot_plan_versions",
        "version_number >= 1 AND total_duration_seconds > 0 AND scene_count BETWEEN 1 AND 60 AND shot_count BETWEEN 1 AND 180",
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)

    op.create_table(
        "planning_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("script_version_id", sa.Uuid(), nullable=True),
        sa.Column("storyboard_version_id", sa.Uuid(), nullable=True),
        sa.Column("shot_plan_version_id", sa.Uuid(), nullable=True),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("requested_changes", postgresql.JSONB(), nullable=False),
        sa.Column("reviewed_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_type IN ('script', 'storyboard', 'shot_plan', 'planning_bundle')",
            name="ck_planning_reviews_artifact_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('approved', 'revision_requested', 'rejected')",
            name="ck_planning_reviews_outcome",
        ),
        sa.CheckConstraint("review_round >= 1", name="ck_planning_reviews_round"),
        sa.CheckConstraint(
            "length(summary) BETWEEN 1 AND 1000 AND jsonb_typeof(requested_changes) = 'object'",
            name="ck_planning_reviews_bounds",
        ),
        sa.CheckConstraint(
            "(artifact_type = 'script' AND script_version_id IS NOT NULL AND storyboard_version_id IS NULL AND shot_plan_version_id IS NULL) OR "
            "(artifact_type = 'storyboard' AND script_version_id IS NULL AND storyboard_version_id IS NOT NULL AND shot_plan_version_id IS NULL) OR "
            "(artifact_type = 'shot_plan' AND script_version_id IS NULL AND storyboard_version_id IS NULL AND shot_plan_version_id IS NOT NULL) OR "
            "(artifact_type = 'planning_bundle' AND script_version_id IS NOT NULL AND storyboard_version_id IS NOT NULL AND shot_plan_version_id IS NOT NULL)",
            name="ck_planning_reviews_artifact_pair",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_planning_reviews_project", ondelete="RESTRICT"
        ),
        _artifact_fk("script_versions", "script_version_id", "fk_planning_reviews_script"),
        _artifact_fk(
            "storyboard_versions", "storyboard_version_id", "fk_planning_reviews_storyboard"
        ),
        _artifact_fk("shot_plan_versions", "shot_plan_version_id", "fk_planning_reviews_shot_plan"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "artifact_type",
            "script_version_id",
            "storyboard_version_id",
            "shot_plan_version_id",
            "review_round",
            name="uq_planning_reviews_round",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_planning_reviews_tenant_id",
        ),
    )

    op.create_table(
        "planning_revision_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("source_script_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_storyboard_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_shot_plan_version_id", sa.Uuid(), nullable=True),
        sa.Column("requested_changes", postgresql.JSONB(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("successor_script_version_id", sa.Uuid(), nullable=True),
        sa.Column("successor_storyboard_version_id", sa.Uuid(), nullable=True),
        sa.Column("successor_shot_plan_version_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "artifact_type IN ('script', 'storyboard', 'shot_plan', 'planning_bundle')",
            name="ck_planning_revision_artifact_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'completed', 'cancelled')",
            name="ck_planning_revision_status",
        ),
        sa.CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="ck_planning_revision_digest"),
        sa.CheckConstraint("version >= 1", name="ck_planning_revision_version"),
        sa.CheckConstraint(
            "jsonb_typeof(requested_changes) = 'object'", name="ck_planning_revision_changes"
        ),
        sa.CheckConstraint(
            "(artifact_type = 'script' AND source_script_version_id IS NOT NULL AND source_storyboard_version_id IS NULL AND source_shot_plan_version_id IS NULL) OR "
            "(artifact_type = 'storyboard' AND source_script_version_id IS NULL AND source_storyboard_version_id IS NOT NULL AND source_shot_plan_version_id IS NULL) OR "
            "(artifact_type = 'shot_plan' AND source_script_version_id IS NULL AND source_storyboard_version_id IS NULL AND source_shot_plan_version_id IS NOT NULL) OR "
            "(artifact_type = 'planning_bundle' AND source_script_version_id IS NOT NULL AND source_storyboard_version_id IS NOT NULL AND source_shot_plan_version_id IS NOT NULL)",
            name="ck_planning_revision_source_pair",
        ),
        sa.CheckConstraint(
            "(status IN ('open', 'cancelled') AND completed_at IS NULL AND successor_script_version_id IS NULL AND successor_storyboard_version_id IS NULL AND successor_shot_plan_version_id IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL AND ((artifact_type = 'script' AND successor_script_version_id IS NOT NULL AND successor_storyboard_version_id IS NULL AND successor_shot_plan_version_id IS NULL) OR (artifact_type = 'storyboard' AND successor_script_version_id IS NULL AND successor_storyboard_version_id IS NOT NULL AND successor_shot_plan_version_id IS NULL) OR (artifact_type = 'shot_plan' AND successor_script_version_id IS NULL AND successor_storyboard_version_id IS NULL AND successor_shot_plan_version_id IS NOT NULL) OR (artifact_type = 'planning_bundle' AND successor_script_version_id IS NOT NULL AND successor_storyboard_version_id IS NOT NULL AND successor_shot_plan_version_id IS NOT NULL)))",
            name="ck_planning_revision_outcome",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_planning_revision_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["review_id"],
            [
                "planning_reviews.organization_id",
                "planning_reviews.workspace_id",
                "planning_reviews.project_id",
                "planning_reviews.id",
            ],
            name="fk_planning_revision_review",
            ondelete="RESTRICT",
        ),
        _artifact_fk(
            "script_versions", "source_script_version_id", "fk_planning_revision_source_script"
        ),
        _artifact_fk(
            "storyboard_versions",
            "source_storyboard_version_id",
            "fk_planning_revision_source_storyboard",
        ),
        _artifact_fk(
            "shot_plan_versions",
            "source_shot_plan_version_id",
            "fk_planning_revision_source_shot_plan",
        ),
        _artifact_fk(
            "script_versions",
            "successor_script_version_id",
            "fk_planning_revision_successor_script",
        ),
        _artifact_fk(
            "storyboard_versions",
            "successor_storyboard_version_id",
            "fk_planning_revision_successor_storyboard",
        ),
        _artifact_fk(
            "shot_plan_versions",
            "successor_shot_plan_version_id",
            "fk_planning_revision_successor_shot_plan",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "review_id",
            name="uq_planning_revision_review",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_planning_revision_tenant_id",
        ),
    )

    op.create_index(
        "uq_planning_reviews_script_round",
        "planning_reviews",
        ["organization_id", "workspace_id", "project_id", "script_version_id", "review_round"],
        unique=True,
        postgresql_where=sa.text("artifact_type = 'script'"),
    )
    op.create_index(
        "uq_planning_reviews_storyboard_round",
        "planning_reviews",
        [
            "organization_id",
            "workspace_id",
            "project_id",
            "storyboard_version_id",
            "review_round",
        ],
        unique=True,
        postgresql_where=sa.text("artifact_type = 'storyboard'"),
    )
    op.create_index(
        "uq_planning_reviews_shot_plan_round",
        "planning_reviews",
        [
            "organization_id",
            "workspace_id",
            "project_id",
            "shot_plan_version_id",
            "review_round",
        ],
        unique=True,
        postgresql_where=sa.text("artifact_type = 'shot_plan'"),
    )
    op.create_index(
        "uq_planning_reviews_bundle_round",
        "planning_reviews",
        [
            "organization_id",
            "workspace_id",
            "project_id",
            "script_version_id",
            "storyboard_version_id",
            "shot_plan_version_id",
            "review_round",
        ],
        unique=True,
        postgresql_where=sa.text("artifact_type = 'planning_bundle'"),
    )

    op.create_table(
        "planning_artifact_revision_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("predecessor_version_id", sa.Uuid(), nullable=False),
        sa.Column("successor_version_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_version_number", sa.Integer(), nullable=False),
        sa.Column("successor_version_number", sa.Integer(), nullable=False),
        sa.Column("revision_request_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_type IN ('script', 'storyboard', 'shot_plan')", name="ck_revision_link_type"
        ),
        sa.CheckConstraint(
            "predecessor_version_number >= 1 AND successor_version_number > predecessor_version_number",
            name="ck_revision_link_versions",
        ),
        sa.CheckConstraint(
            "predecessor_version_id <> successor_version_id", name="ck_revision_link_distinct"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_revision_link_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["revision_request_id"],
            [
                "planning_revision_requests.organization_id",
                "planning_revision_requests.workspace_id",
                "planning_revision_requests.project_id",
                "planning_revision_requests.id",
            ],
            name="fk_revision_link_request",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "predecessor_version_id",
            name="uq_revision_link_predecessor",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "successor_version_id",
            name="uq_revision_link_successor",
        ),
    )

    op.create_table(
        "delivery_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("version >= 1", name="ck_delivery_packages_version"),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_delivery_packages_project", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_delivery_packages_tenant_id",
        ),
    )

    op.create_table(
        "delivery_package_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_package_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("script_version_id", sa.Uuid(), nullable=False),
        sa.Column("storyboard_version_id", sa.Uuid(), nullable=False),
        sa.Column("shot_plan_version_id", sa.Uuid(), nullable=False),
        sa.Column("approval_review_id", sa.Uuid(), nullable=False),
        sa.Column("script_content_digest", sa.String(64), nullable=False),
        sa.Column("storyboard_content_digest", sa.String(64), nullable=False),
        sa.Column("shot_plan_content_digest", sa.String(64), nullable=False),
        sa.Column("manifest_schema_version", sa.String(30), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("version_number >= 1", name="ck_delivery_package_version_number"),
        sa.CheckConstraint(
            "script_content_digest ~ '^[0-9a-f]{64}$' AND storyboard_content_digest ~ '^[0-9a-f]{64}$' AND shot_plan_content_digest ~ '^[0-9a-f]{64}$' AND manifest_digest ~ '^[0-9a-f]{64}$'",
            name="ck_delivery_package_digests",
        ),
        sa.CheckConstraint(
            "manifest_schema_version = 'delivery-package-v1' AND jsonb_typeof(manifest) = 'object'",
            name="ck_delivery_package_manifest",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_delivery_package_versions_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["delivery_package_id"],
            [
                "delivery_packages.organization_id",
                "delivery_packages.workspace_id",
                "delivery_packages.project_id",
                "delivery_packages.id",
            ],
            name="fk_delivery_package_versions_package",
            ondelete="RESTRICT",
        ),
        _artifact_fk("script_versions", "script_version_id", "fk_delivery_package_versions_script"),
        _artifact_fk(
            "storyboard_versions",
            "storyboard_version_id",
            "fk_delivery_package_versions_storyboard",
        ),
        _artifact_fk(
            "shot_plan_versions", "shot_plan_version_id", "fk_delivery_package_versions_shot_plan"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["approval_review_id"],
            [
                "planning_reviews.organization_id",
                "planning_reviews.workspace_id",
                "planning_reviews.project_id",
                "planning_reviews.id",
            ],
            name="fk_delivery_package_versions_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["supersedes_version_id"],
            [
                "delivery_package_versions.organization_id",
                "delivery_package_versions.workspace_id",
                "delivery_package_versions.project_id",
                "delivery_package_versions.id",
            ],
            name="fk_delivery_package_versions_supersedes",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "delivery_package_id", "version_number", name="uq_delivery_package_versions_number"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_delivery_package_versions_tenant_id",
        ),
    )
    op.create_foreign_key(
        "fk_delivery_packages_current_version",
        "delivery_packages",
        "delivery_package_versions",
        ["organization_id", "workspace_id", "project_id", "current_version_id"],
        ["organization_id", "workspace_id", "project_id", "id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "delivery_export_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_package_version_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(120), nullable=False),
        sa.Column("storage_adapter", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "format IN ('manifest.json', 'script.json', 'storyboard.json', 'shot-plan.json', 'shot-plan.csv', 'README.txt', 'delivery-package.zip')",
            name="ck_delivery_export_format",
        ),
        sa.CheckConstraint(
            "filename !~ '[\\\\/]' AND filename !~ '\\.\\.'", name="ck_delivery_export_filename"
        ),
        sa.CheckConstraint(
            "storage_key ~ '^object-[A-Za-z0-9]{32}$'", name="ck_delivery_export_storage_key"
        ),
        sa.CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$' AND byte_size > 0 AND byte_size <= 10485760",
            name="ck_delivery_export_bounds",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_delivery_export_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["delivery_package_version_id"],
            [
                "delivery_package_versions.organization_id",
                "delivery_package_versions.workspace_id",
                "delivery_package_versions.project_id",
                "delivery_package_versions.id",
            ],
            name="fk_delivery_export_package_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_adapter", "storage_key", name="uq_delivery_export_storage_key"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "delivery_package_version_id",
            "format",
            name="uq_delivery_export_format",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_delivery_export_tenant_id",
        ),
    )

    op.create_table(
        "delivery_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("outcome_review_id", sa.Uuid(), nullable=True),
        sa.Column("outcome_revision_request_id", sa.Uuid(), nullable=True),
        sa.Column("outcome_delivery_package_id", sa.Uuid(), nullable=True),
        sa.Column("outcome_delivery_package_version_id", sa.Uuid(), nullable=True),
        sa.Column("outcome_export_file_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_by_actor_subject", sa.String(200), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "operation IN ('submit_planning_review', 'create_revision_request', 'complete_revision_request', 'create_delivery_package', 'export_delivery_package')",
            name="ck_delivery_operation_type",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted')", name="ck_delivery_operation_status"
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'", name="ck_delivery_operation_digest"
        ),
        sa.CheckConstraint("version >= 1", name="ck_delivery_operation_version"),
        sa.CheckConstraint(
            "(status = 'reserved' AND completed_at IS NULL AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR "
            "(status = 'accepted' AND completed_at IS NOT NULL AND ((operation = 'submit_planning_review' AND outcome_review_id IS NOT NULL AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR (operation = 'create_revision_request' AND outcome_review_id IS NOT NULL AND outcome_revision_request_id IS NOT NULL AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR (operation = 'complete_revision_request' AND outcome_revision_request_id IS NOT NULL AND outcome_review_id IS NULL AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL AND outcome_export_file_id IS NULL) OR (operation = 'create_delivery_package' AND outcome_delivery_package_id IS NOT NULL AND outcome_delivery_package_version_id IS NOT NULL AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL AND outcome_export_file_id IS NULL) OR (operation = 'export_delivery_package' AND outcome_export_file_id IS NOT NULL AND outcome_delivery_package_id IS NULL AND outcome_delivery_package_version_id IS NULL AND outcome_review_id IS NULL AND outcome_revision_request_id IS NULL)))",
            name="ck_delivery_operation_outcome",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE, _PROJECT_REF, name="fk_delivery_operation_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["outcome_review_id"],
            [
                "planning_reviews.organization_id",
                "planning_reviews.workspace_id",
                "planning_reviews.project_id",
                "planning_reviews.id",
            ],
            name="fk_delivery_operation_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["outcome_revision_request_id"],
            [
                "planning_revision_requests.organization_id",
                "planning_revision_requests.workspace_id",
                "planning_revision_requests.project_id",
                "planning_revision_requests.id",
            ],
            name="fk_delivery_operation_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["outcome_delivery_package_id"],
            [
                "delivery_packages.organization_id",
                "delivery_packages.workspace_id",
                "delivery_packages.project_id",
                "delivery_packages.id",
            ],
            name="fk_delivery_operation_package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["outcome_delivery_package_version_id"],
            [
                "delivery_package_versions.organization_id",
                "delivery_package_versions.workspace_id",
                "delivery_package_versions.project_id",
                "delivery_package_versions.id",
            ],
            name="fk_delivery_operation_package_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            _SCOPE + ["outcome_export_file_id"],
            [
                "delivery_export_files.organization_id",
                "delivery_export_files.workspace_id",
                "delivery_export_files.project_id",
                "delivery_export_files.id",
            ],
            name="fk_delivery_operation_export",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_delivery_operation_key",
        ),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_planning_revision_link() RETURNS trigger AS $$
        DECLARE predecessor_exists boolean; successor_exists boolean;
        BEGIN
          IF NEW.artifact_type = 'script' THEN
            SELECT EXISTS (SELECT 1 FROM script_versions WHERE organization_id=NEW.organization_id AND workspace_id=NEW.workspace_id AND project_id=NEW.project_id AND id=NEW.predecessor_version_id),
                   EXISTS (SELECT 1 FROM script_versions WHERE organization_id=NEW.organization_id AND workspace_id=NEW.workspace_id AND project_id=NEW.project_id AND id=NEW.successor_version_id) INTO predecessor_exists, successor_exists;
          ELSIF NEW.artifact_type = 'storyboard' THEN
            SELECT EXISTS (SELECT 1 FROM storyboard_versions WHERE organization_id=NEW.organization_id AND workspace_id=NEW.workspace_id AND project_id=NEW.project_id AND id=NEW.predecessor_version_id),
                   EXISTS (SELECT 1 FROM storyboard_versions WHERE organization_id=NEW.organization_id AND workspace_id=NEW.workspace_id AND project_id=NEW.project_id AND id=NEW.successor_version_id) INTO predecessor_exists, successor_exists;
          ELSE
            SELECT EXISTS (SELECT 1 FROM shot_plan_versions WHERE organization_id=NEW.organization_id AND workspace_id=NEW.workspace_id AND project_id=NEW.project_id AND id=NEW.predecessor_version_id),
                   EXISTS (SELECT 1 FROM shot_plan_versions WHERE organization_id=NEW.organization_id AND workspace_id=NEW.workspace_id AND project_id=NEW.project_id AND id=NEW.successor_version_id) INTO predecessor_exists, successor_exists;
          END IF;
          IF NOT predecessor_exists OR NOT successor_exists THEN RAISE EXCEPTION 'revision link artifact is not in tenant scope'; END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE CONSTRAINT TRIGGER trg_planning_revision_link_scope
        AFTER INSERT OR UPDATE ON planning_artifact_revision_links
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_planning_revision_link();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_planning_revision_link_scope ON planning_artifact_revision_links"
    )
    op.execute("DROP FUNCTION IF EXISTS check_planning_revision_link()")
    op.drop_table("delivery_operations")
    op.drop_table("delivery_export_files")
    op.drop_constraint(
        "fk_delivery_packages_current_version", "delivery_packages", type_="foreignkey"
    )
    op.drop_table("delivery_package_versions")
    op.drop_table("delivery_packages")
    op.drop_table("planning_artifact_revision_links")
    op.drop_table("planning_revision_requests")
    op.execute("DROP INDEX IF EXISTS uq_planning_reviews_bundle_round")
    op.execute("DROP INDEX IF EXISTS uq_planning_reviews_shot_plan_round")
    op.execute("DROP INDEX IF EXISTS uq_planning_reviews_storyboard_round")
    op.execute("DROP INDEX IF EXISTS uq_planning_reviews_script_round")
    op.drop_table("planning_reviews")
    op.drop_constraint("ck_shot_plan_version_bounds", "shot_plan_versions", type_="check")
    op.create_check_constraint(
        "ck_shot_plan_version_bounds",
        "shot_plan_versions",
        "version_number = 1 AND total_duration_seconds > 0 AND scene_count BETWEEN 1 AND 60 AND shot_count BETWEEN 1 AND 180",
    )
    op.drop_constraint("ck_storyboard_version_bounds", "storyboard_versions", type_="check")
    op.create_check_constraint(
        "ck_storyboard_version_bounds",
        "storyboard_versions",
        "version_number = 1 AND total_duration_seconds > 0 AND scene_count BETWEEN 1 AND 60",
    )
    op.drop_constraint("ck_script_version_number", "script_versions", type_="check")
    op.create_check_constraint("ck_script_version_number", "script_versions", "version_number = 1")
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
