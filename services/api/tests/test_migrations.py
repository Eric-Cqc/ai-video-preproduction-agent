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
    assert revision == "9031dcffc3ea"
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
        "source_objects",
        "source_object_uploads",
        "source_object_cleanup_requirements",
        "document_extractions",
        "document_extraction_operations",
        "brief_extraction_runs",
        "brief_extraction_attempts",
        "brief_candidate_reviews",
        "creative_concept_runs",
        "creative_concept_candidates",
        "creative_concept_selections",
        "creative_generation_operations",
        "script_runs",
        "script_versions",
        "storyboard_runs",
        "storyboard_versions",
        "shot_plan_runs",
        "shot_plan_versions",
        "visual_planning_operations",
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


def test_visual_planning_lineage_and_operation_constraints_exist(
    database_engine: Engine,
) -> None:
    expected = {
        "uq_script_versions_lineage",
        "uq_storyboard_runs_lineage",
        "fk_storyboard_runs_script_version",
        "uq_storyboard_versions_lineage",
        "fk_storyboard_versions_run",
        "uq_shot_plan_runs_lineage",
        "fk_shot_plan_runs_storyboard",
        "fk_shot_plan_versions_run",
        "fk_visual_operation_storyboard_run",
        "fk_visual_operation_storyboard_version",
        "fk_visual_operation_shot_run",
        "fk_visual_operation_shot_version",
        "ck_visual_operation_outcome",
    }
    with database_engine.connect() as connection:
        constraints = set(
            connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname = ANY(:names) "
                    "AND connamespace = 'public'::regnamespace"
                ),
                {"names": list(expected)},
            )
        )
    assert constraints == expected
