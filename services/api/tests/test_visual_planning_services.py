import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.errors import ApplicationError
from services.api.app.application.model_provider import DeterministicVisualPlanningProvider
from services.api.app.application.visual_planning_services import (
    SHOT_PLAN_PROMPT_INSTRUCTIONS,
    STORYBOARD_PROMPT_INSTRUCTIONS,
    VisualPlanningApplicationService,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_visual_planning_persistence import (
    _insert_script_graph,
    _seed_project,
)

SCRIPT_FIXTURE = (
    Path(__file__).resolve().parents[3] / "packages/test-fixtures/creative/valid-script-v1.json"
)


def _service(session_factory: SessionFactory) -> VisualPlanningApplicationService:
    return VisualPlanningApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory), DeterministicVisualPlanningProvider()
    )


def _make_script_usable(engine: Engine, script_version_id: object) -> None:
    content = json.loads(SCRIPT_FIXTURE.read_text())
    import hashlib

    digest = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE script_versions SET content=:content, content_digest=:digest WHERE id=:id"
            ),
            {"content": json.dumps(content), "digest": digest, "id": script_version_id},
        )


def test_storyboard_and_shot_plan_generation_chain(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory, name="Stage 12B service")
    graph = _insert_script_graph(database_engine, seed, "stage12b")
    _make_script_usable(database_engine, graph.script_version_id)
    service = _service(persistence_session_factory)

    storyboard = service.generate_storyboard(
        seed.context, seed.project_id, graph.script_version_id, idempotency_key="stage12b-board"
    )
    assert storyboard.replayed is False
    assert storyboard.version.scene_count == 1
    replay = service.generate_storyboard(
        seed.context, seed.project_id, graph.script_version_id, idempotency_key="stage12b-board"
    )
    assert replay.replayed is True
    assert replay.run.id == storyboard.run.id
    shot_plan = service.generate_shot_plan(
        seed.context,
        seed.project_id,
        storyboard.version.id,
        idempotency_key="stage12b-shots",
    )
    assert shot_plan.replayed is False
    assert shot_plan.version.shot_count == 1
    assert shot_plan.version.storyboard_version_id == storyboard.version.id


def test_visual_planning_prompts_define_exact_schema_and_lineage() -> None:
    assert "exactly one storyboard scene" in STORYBOARD_PROMPT_INSTRUCTIONS
    assert "source_script_scene_number must equal" in STORYBOARD_PROMPT_INSTRUCTIONS
    assert "exactly one shot" in SHOT_PLAN_PROMPT_INSTRUCTIONS
    assert "estimated_duration_seconds must equal" in SHOT_PLAN_PROMPT_INSTRUCTIONS


@pytest.mark.parametrize(
    "mode",
    [
        "malformed_json",
        "markdown_wrapped",
        "schema_invalid",
        "duration_mismatch",
        "refusal",
        "timeout",
        "provider_error",
    ],
)
def test_storyboard_invalid_provider_modes_rollback(
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    clean_database: None,
    mode: str,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory, name=f"Stage 12B {mode}")
    graph = _insert_script_graph(database_engine, seed, mode)
    _make_script_usable(database_engine, graph.script_version_id)
    service = _service(persistence_session_factory)
    with pytest.raises(ApplicationError):
        service.generate_storyboard(
            seed.context,
            seed.project_id,
            graph.script_version_id,
            idempotency_key=f"rollback-{mode}",
            provider_mode=mode,
        )
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM visual_planning_operations")) == 0
        assert connection.scalar(text("SELECT count(*) FROM storyboard_runs")) == 0
