"""create source asset metadata boundary

Revision ID: c4f1d2a9b8e7
Revises: b2a7c9d1e4f0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4f1d2a9b8e7"
down_revision: str | None = "b2a7c9d1e4f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_REFERENCE_CHECK = (
    "(source_reference IS NULL OR (length(btrim(source_reference)) > 0 AND "
    "source_reference !~ '[[:cntrl:]]' AND "
    "source_reference !~ '(^/|^~/|^[A-Za-z]:\\\\|^\\\\\\\\|^file://|"
    "^postgres(ql)?://|^mysql://|^mongodb(\\\\+srv)?://|"
    "^[A-Za-z][A-Za-z0-9+.-]*://[^/[:space:]]*@)' AND "
    "source_reference !~* '(authorization|bearer|token|access[_-]?token|"
    "refresh[_-]?token|api[_-]?key|secret|password|"
    "(\\\\?|&)(x-amz-signature|x-goog-signature|signature|sig|token|"
    "access_token)=)'))"
)
_EXTERNAL_RECORD_ID_CHECK = (
    "(external_record_id IS NULL OR (length(btrim(external_record_id)) > 0 AND "
    "external_record_id !~ '[[:cntrl:]]' AND "
    "external_record_id !~ '(^/|^~/|^[A-Za-z]:\\\\|^\\\\\\\\|^file://|"
    "^postgres(ql)?://|^mysql://|^mongodb(\\\\+srv)?://|"
    "^[A-Za-z][A-Za-z0-9+.-]*://[^/[:space:]]*@)' AND "
    "external_record_id !~* '(authorization|bearer|token|access[_-]?token|"
    "refresh[_-]?token|api[_-]?key|secret|password|"
    "(\\\\?|&)(x-amz-signature|x-goog-signature|signature|sig|token|"
    "access_token)=)'))"
)


def upgrade() -> None:
    op.create_table(
        "source_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=False),
        sa.Column("latest_version_number", sa.Integer(), nullable=False),
        sa.Column("created_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_source_asset_status"),
        sa.CheckConstraint("latest_version_number >= 1", name="ck_source_asset_latest_version"),
        sa.CheckConstraint("version >= 1", name="ck_source_asset_version"),
        sa.CheckConstraint(
            "length(btrim(display_name)) > 0 AND display_name !~ '[[:cntrl:]]'",
            name="ck_source_asset_display_name",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="source_assets_organization_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_source_assets_workspace_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id"],
            ["projects.organization_id", "projects.workspace_id", "projects.id"],
            name="fk_source_assets_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "id",
            name="uq_source_assets_tenant_project_id",
        ),
    )
    op.create_index(
        "ix_source_assets_tenant_project",
        "source_assets",
        ["organization_id", "workspace_id", "project_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "source_asset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum_algorithm", sa.String(length=20), nullable=False),
        sa.Column("checksum_value", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("external_record_id", sa.String(length=200), nullable=True),
        sa.Column("declared_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_actor_subject", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.Column("metadata_schema_version", sa.String(length=20), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="ck_source_asset_version_number"),
        sa.CheckConstraint(
            "byte_size > 0 AND byte_size <= 104857600",
            name="ck_source_asset_version_byte_size",
        ),
        sa.CheckConstraint(
            "checksum_algorithm = 'sha256'",
            name="ck_source_asset_version_checksum_algorithm",
        ),
        sa.CheckConstraint(
            "checksum_value ~ '^[0-9a-f]{64}$'",
            name="ck_source_asset_version_checksum_value",
        ),
        sa.CheckConstraint(
            "media_type IN ('application/pdf', "
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', "
            "'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', "
            "'text/plain', 'text/csv', 'application/json')",
            name="ck_source_asset_version_media_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('manual_metadata', 'external_system', 'api_declared')",
            name="ck_source_asset_version_source_type",
        ),
        sa.CheckConstraint(
            "metadata_schema_version = '1.0.0'",
            name="ck_source_asset_version_metadata_schema_version",
        ),
        sa.CheckConstraint(
            "length(btrim(original_filename)) > 0 AND "
            "original_filename !~ '[[:cntrl:]/\\\\]' AND original_filename NOT LIKE '%..%'",
            name="ck_source_asset_version_filename",
        ),
        sa.CheckConstraint(
            _SOURCE_REFERENCE_CHECK,
            name="ck_source_asset_version_source_reference",
        ),
        sa.CheckConstraint(
            _EXTERNAL_RECORD_ID_CHECK,
            name="ck_source_asset_version_external_record_id",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "project_id", "source_asset_id"],
            [
                "source_assets.organization_id",
                "source_assets.workspace_id",
                "source_assets.project_id",
                "source_assets.id",
            ],
            name="fk_source_asset_versions_asset_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "workspace_id",
                "project_id",
                "source_asset_id",
                "supersedes_version_id",
            ],
            [
                "source_asset_versions.organization_id",
                "source_asset_versions.workspace_id",
                "source_asset_versions.project_id",
                "source_asset_versions.source_asset_id",
                "source_asset_versions.id",
            ],
            name="fk_source_asset_versions_supersedes",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_asset_id", "version_number", name="uq_source_asset_versions_number"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "project_id",
            "source_asset_id",
            "id",
            name="uq_source_asset_versions_tenant_asset_id",
        ),
    )
    op.create_index(
        "ix_source_asset_versions_tenant_asset",
        "source_asset_versions",
        ["organization_id", "workspace_id", "project_id", "source_asset_id", "version_number"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_source_assets_current_version",
        "source_assets",
        "source_asset_versions",
        ["organization_id", "workspace_id", "project_id", "id", "current_version_id"],
        ["organization_id", "workspace_id", "project_id", "source_asset_id", "id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint("fk_source_assets_current_version", "source_assets", type_="foreignkey")
    op.drop_table("source_asset_versions")
    op.drop_table("source_assets")
