"""create binary object storage boundary

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_AUDIT_ACTION = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
    "'brief.issue_dismissed', 'brief.ingestion_accepted', "
    "'brief_ingestion.source_attached', 'source_asset.created', "
    "'source_asset.version_created', 'source_asset.archived')"
)
_NEW_AUDIT_ACTION = _OLD_AUDIT_ACTION[:-1] + ", 'source_object.uploaded')"


def upgrade() -> None:
    op.create_table(
        "source_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("storage_adapter", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("observed_byte_size", sa.Integer(), nullable=False),
        sa.Column("observed_checksum_algorithm", sa.String(20), nullable=False),
        sa.Column("observed_checksum_value", sa.String(64), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_source_objects_tenant_project_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
            name="uq_source_objects_source_version",
        ),
        sa.UniqueConstraint("storage_adapter", "storage_key", name="uq_source_objects_storage_key"),
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
            name="fk_source_objects_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("state = 'available'", name="ck_source_object_state"),
        sa.CheckConstraint(
            "observed_byte_size > 0 AND observed_byte_size <= 104857600",
            name="ck_source_object_byte_size",
        ),
        sa.CheckConstraint(
            "observed_checksum_algorithm = 'sha256'", name="ck_source_object_checksum_algorithm"
        ),
        sa.CheckConstraint(
            "observed_checksum_value ~ '^[0-9a-f]{64}$'", name="ck_source_object_checksum_value"
        ),
        sa.CheckConstraint("version >= 1", name="ck_source_object_version"),
    )
    op.create_index(
        "ix_source_objects_tenant_version",
        "source_objects",
        [
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
        ],
    )
    op.create_table(
        "source_object_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_object_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("submitted_by_actor_subject", sa.String(200), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "operation",
            "idempotency_key",
            name="uq_source_object_uploads_idempotency",
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
            name="fk_source_object_uploads_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_object_id"],
            [
                "source_objects.organization_id",
                "source_objects.workspace_id",
                "source_objects.project_id",
                "source_objects.id",
            ],
            name="fk_source_object_uploads_object_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "operation = 'upload_source_object'", name="ck_source_object_upload_operation"
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted')", name="ck_source_object_upload_status"
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'", name="ck_source_object_upload_digest"
        ),
        sa.CheckConstraint("version >= 1", name="ck_source_object_upload_version"),
        sa.CheckConstraint(
            "(status = 'reserved' AND source_object_id IS NULL "
            "AND completed_at IS NULL) OR (status = 'accepted' "
            "AND source_object_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_source_object_upload_outcome",
        ),
    )
    op.create_table(
        "source_object_cleanup_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("storage_adapter", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_source_object_cleanup_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "storage_adapter", "storage_key", name="uq_source_object_cleanup_storage_key"
        ),
        sa.CheckConstraint(
            "reason_code IN ('database_failure', 'replay_cleanup_failure', "
            "'staging_cleanup_failure')",
            name="ck_source_object_cleanup_reason",
        ),
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_action",
        "audit_events",
        _NEW_AUDIT_ACTION,
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_action",
        "audit_events",
        _OLD_AUDIT_ACTION,
    )
    op.drop_table("source_object_cleanup_requirements")
    op.drop_table("source_object_uploads")
    op.drop_index("ix_source_objects_tenant_version", table_name="source_objects")
    op.drop_table("source_objects")
