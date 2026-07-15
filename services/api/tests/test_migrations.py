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
    assert revision == "fca964a30853"
    assert tables == {"organizations", "workspaces", "memberships", "projects", "audit_events"}


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
