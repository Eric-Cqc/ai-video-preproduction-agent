"""create document extraction foundation

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_AUDIT = (
    "action IN ('organization.created', 'workspace.created', 'membership.created', "
    "'project.created', 'project.updated', 'project.activated', 'project.archived', "
    "'brief.created', 'brief.version_created', 'brief.submitted_for_review', "
    "'brief.approved', 'brief.archived', 'brief.issue_created', 'brief.issue_resolved', "
    "'brief.issue_dismissed', 'brief.ingestion_accepted', "
    "'brief_ingestion.source_attached', 'source_asset.created', "
    "'source_asset.version_created', 'source_asset.archived', 'source_object.uploaded')"
)
_NEW_AUDIT = _OLD_AUDIT[:-1] + ", 'document_extraction.completed')"


def upgrade() -> None:
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_object_id", sa.Uuid(), nullable=False),
        sa.Column("parser_id", sa.String(60), nullable=False),
        sa.Column("parser_version", sa.String(20), nullable=False),
        sa.Column("source_checksum_algorithm", sa.String(20), nullable=False),
        sa.Column("source_checksum_value", sa.String(64), nullable=False),
        sa.Column("options_digest", sa.String(64), nullable=False),
        sa.Column("extraction_checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("extracted_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_actor_subject", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_document_extractions_tenant_project_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
            "parser_id",
            "parser_version",
            "options_digest",
            name="uq_document_extractions_parser_result",
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
            name="fk_document_extractions_version_tenant",
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
            name="fk_document_extractions_object_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("status = 'completed'", name="ck_document_extraction_status"),
        sa.CheckConstraint(
            "source_checksum_algorithm = 'sha256'",
            name="ck_document_extraction_source_checksum_algorithm",
        ),
        sa.CheckConstraint(
            "source_checksum_value ~ '^[0-9a-f]{64}$' "
            "AND options_digest ~ '^[0-9a-f]{64}$' "
            "AND extraction_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_document_extraction_digests",
        ),
        sa.CheckConstraint(
            "character_count >= 0 AND character_count <= 1048576",
            name="ck_document_extraction_character_count",
        ),
        sa.CheckConstraint("warning_count >= 0", name="ck_document_extraction_warning_count"),
        sa.CheckConstraint("truncated = false", name="ck_document_extraction_not_truncated"),
        sa.CheckConstraint(
            "schema_version = '1.0.0'", name="ck_document_extraction_schema_version"
        ),
    )
    op.create_index(
        "ix_document_extractions_tenant_source_version",
        "document_extractions",
        [
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "source_asset_version_id",
            "created_at",
        ],
    )
    op.create_table(
        "document_extraction_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_id", sa.Uuid(), nullable=True),
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
            "idempotency_key",
            name="uq_document_extraction_operations_idempotency",
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
            name="fk_document_extraction_operations_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.project_id",
                "document_extractions.id",
            ],
            name="fk_document_extraction_operations_result_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'", name="ck_document_extraction_operation_digest"
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'accepted')", name="ck_document_extraction_operation_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_document_extraction_operation_version"),
        sa.CheckConstraint(
            "(status='reserved' AND extraction_id IS NULL "
            "AND completed_at IS NULL) OR (status='accepted' "
            "AND extraction_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_document_extraction_operation_outcome",
        ),
    )
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _NEW_AUDIT)


def downgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", _OLD_AUDIT)
    op.drop_table("document_extraction_operations")
    op.drop_index(
        "ix_document_extractions_tenant_source_version", table_name="document_extractions"
    )
    op.drop_table("document_extractions")
