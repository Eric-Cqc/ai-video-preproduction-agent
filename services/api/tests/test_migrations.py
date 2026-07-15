from sqlalchemy import Engine, text


def test_database_schema_is_at_expected_migration_head(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = set(
            connection.scalars(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        )
    assert revision == "f1a2b3c4d5e6"
    assert tables == {
        "organizations",
        "workspaces",
        "memberships",
        "projects",
        "briefs",
        "brief_versions",
        "requirement_issues",
        "audit_events",
        "brief_ingestions",
        "source_assets",
        "source_asset_versions",
        "source_asset_operations",
        "brief_ingestion_source_assets",
    }


def test_membership_partial_unique_indexes_exist(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'memberships' "
                "AND indexname LIKE 'uq_memberships_%'"
            )
        ).mappings()
        definitions: dict[str, str] = {str(row["indexname"]): str(row["indexdef"]) for row in rows}
    assert "WHERE (workspace_id IS NULL)" in definitions["uq_memberships_org_actor"]
    assert "WHERE (workspace_id IS NOT NULL)" in definitions["uq_memberships_workspace_actor"]


def test_brief_current_pointer_is_same_aggregate_and_deferred(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        constraint = (
            connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) AS definition, condeferrable, condeferred "
                    "FROM pg_constraint WHERE conname = 'fk_briefs_current_version'"
                )
            )
            .mappings()
            .one()
        )
    definition = str(constraint["definition"])
    assert (
        "FOREIGN KEY (organization_id, workspace_id, project_id, id, current_version_id)"
        in definition
    )
    assert "brief_versions(organization_id, workspace_id, project_id, brief_id, id)" in definition
    assert constraint["condeferrable"] is True
    assert constraint["condeferred"] is True


def test_source_asset_current_pointer_is_same_aggregate_and_deferred(
    database_engine: Engine,
) -> None:
    with database_engine.connect() as connection:
        constraint = (
            connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) AS definition, condeferrable, condeferred "
                    "FROM pg_constraint WHERE conname = 'fk_source_assets_current_version'"
                )
            )
            .mappings()
            .one()
        )
    definition = str(constraint["definition"])
    assert (
        "FOREIGN KEY (organization_id, workspace_id, project_id, id, current_version_id)"
        in definition
    )
    assert (
        "source_asset_versions(organization_id, workspace_id, project_id, source_asset_id, id)"
        in definition
    )
    assert constraint["condeferrable"] is True
    assert constraint["condeferred"] is True
