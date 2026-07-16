import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def require_test_database_url(database_url: str) -> str:
    url = make_url(database_url)
    database_name = url.database or ""
    if url.get_backend_name() != "postgresql" or not database_name.endswith("_test"):
        raise RuntimeError("refusing to use a database whose name does not end in _test")
    return database_url


def main() -> int:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        raise RuntimeError("TEST_DATABASE_URL is required")
    database_url = require_test_database_url(database_url)

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE visual_planning_operations, shot_plan_versions, "
                    "shot_plan_runs, storyboard_versions, storyboard_runs, "
                    "creative_generation_operations, script_versions, script_runs, "
                    "creative_concept_selections, creative_concept_candidates, "
                    "creative_concept_runs, "
                    "brief_candidate_reviews, brief_extraction_attempts, "
                    "brief_extraction_runs, "
                    "document_extraction_operations, document_extractions, "
                    "brief_ingestion_source_assets, source_asset_operations, "
                    "source_object_uploads, source_object_cleanup_requirements, source_objects, "
                    "source_asset_versions, source_assets, brief_ingestions, requirement_issues, "
                    "brief_versions, briefs, audit_events, projects, memberships, workspaces, "
                    "organizations CASCADE"
                )
            )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
