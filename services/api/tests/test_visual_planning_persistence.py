import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DataError, IntegrityError

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.context import ActorContext, OrganizationContext, TenantContext
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import (
    BriefSourceType,
    CreativeRunStatus,
    ShotPlanRun,
    ShotPlanVersion,
    StoryboardRun,
    StoryboardVersion,
    VersionConflict,
    VisualPlanningOperation,
    VisualPlanningOperationStatus,
    VisualPlanningOperationType,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.app.infrastructure.visual_planning_repositories import (
    SqlAlchemyVisualPlanningOperationRepository,
)

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
)


@dataclass(frozen=True, slots=True)
class ProjectSeed:
    context: TenantContext
    project_id: UUID
    brief_id: UUID
    brief_version_id: UUID


@dataclass(frozen=True, slots=True)
class ScriptGraph:
    seed: ProjectSeed
    concept_run_id: UUID
    concept_candidate_id: UUID
    concept_selection_id: UUID
    script_run_id: UUID
    script_version_id: UUID
    script_content_digest: str


@dataclass(frozen=True, slots=True)
class StoryboardGraph:
    script: ScriptGraph
    run_id: UUID
    version_id: UUID
    content_digest: str


@dataclass(frozen=True, slots=True)
class ShotPlanGraph:
    storyboard: StoryboardGraph
    run_id: UUID
    version_id: UUID
    content_digest: str


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _seed_project(session_factory: SessionFactory, *, name: str = "Visual") -> ProjectSeed:
    service = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory))
    actor = ActorContext(f"actor:{uuid4().hex}", f"visual-{uuid4().hex}")
    organization = service.create_organization(actor, slug=f"org-{uuid4().hex[:8]}", name="Org")
    org_context = OrganizationContext(actor.actor_subject, actor.correlation_id, organization.id)
    workspace = service.create_workspace(org_context, slug=f"ws-{uuid4().hex[:8]}", name="Main")
    context = TenantContext(
        actor.actor_subject, actor.correlation_id, organization.id, workspace.id
    )
    project = service.create_project(context, name=name, description=None)
    brief = BriefApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory)).create_brief(
        context,
        project.id,
        title=f"{name} brief",
        structured_content=json.loads(FIXTURE.read_text()),
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Initial",
    )
    return ProjectSeed(context, project.id, brief.brief.id, brief.current_version.id)


def _insert_script_graph(engine: Engine, seed: ProjectSeed, key: str) -> ScriptGraph:
    now = datetime.now(UTC)
    concept_run_id = uuid4()
    candidate_id = uuid4()
    selection_id = uuid4()
    script_run_id = uuid4()
    script_version_id = uuid4()
    script_digest = _digest(f"script-{key}")
    values = {
        "organization_id": seed.context.organization_id,
        "workspace_id": seed.context.workspace_id,
        "project_id": seed.project_id,
        "brief_id": seed.brief_id,
        "brief_version_id": seed.brief_version_id,
        "concept_run_id": concept_run_id,
        "candidate_id": candidate_id,
        "selection_id": selection_id,
        "script_run_id": script_run_id,
        "script_version_id": script_version_id,
        "brief_digest": _digest(f"brief-{key}"),
        "concept_digest": _digest(f"concept-{key}"),
        "script_digest": script_digest,
        "actor": seed.context.actor_subject,
        "now": now,
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO creative_concept_runs "
                "(id, organization_id, workspace_id, project_id, brief_id, brief_version_id, "
                "brief_content_digest, instruction_template_id, instruction_template_version, "
                "provider_id, model_id, candidate_count, status, failure_category, "
                "created_by_actor_subject, created_at, completed_at, version) VALUES "
                "(:concept_run_id, :organization_id, :workspace_id, :project_id, :brief_id, "
                ":brief_version_id, :brief_digest, 'template', '1', 'offline', 'fake', 3, "
                "'completed', NULL, :actor, :now, :now, 1)"
            ),
            values,
        )
        connection.execute(
            text(
                "INSERT INTO creative_concept_candidates "
                "(id, organization_id, workspace_id, project_id, concept_run_id, "
                "candidate_index, schema_version, content, content_digest, created_at) VALUES "
                "(:candidate_id, :organization_id, :workspace_id, :project_id, "
                ":concept_run_id, 1, '1.0.0', CAST(:content AS jsonb), :concept_digest, :now)"
            ),
            values | {"content": json.dumps({"title": key})},
        )
        connection.execute(
            text(
                "INSERT INTO creative_concept_selections "
                "(id, organization_id, workspace_id, project_id, concept_run_id, "
                "concept_candidate_id, selected_by_actor_subject, selected_at, version) VALUES "
                "(:selection_id, :organization_id, :workspace_id, :project_id, "
                ":concept_run_id, :candidate_id, :actor, :now, 1)"
            ),
            values,
        )
        connection.execute(
            text(
                "INSERT INTO script_runs "
                "(id, organization_id, workspace_id, project_id, brief_id, brief_version_id, "
                "concept_run_id, concept_candidate_id, concept_selection_id, "
                "brief_content_digest, concept_content_digest, instruction_template_id, "
                "instruction_template_version, provider_id, model_id, status, failure_category, "
                "created_by_actor_subject, created_at, completed_at, version) VALUES "
                "(:script_run_id, :organization_id, :workspace_id, :project_id, :brief_id, "
                ":brief_version_id, :concept_run_id, :candidate_id, :selection_id, "
                ":brief_digest, :concept_digest, 'template', '1', 'offline', 'fake', "
                "'completed', NULL, :actor, :now, :now, 1)"
            ),
            values,
        )
        connection.execute(
            text(
                "INSERT INTO script_versions "
                "(id, organization_id, workspace_id, project_id, script_run_id, brief_id, "
                "brief_version_id, concept_run_id, concept_candidate_id, concept_selection_id, "
                "version_number, schema_version, content, content_digest, created_at) VALUES "
                "(:script_version_id, :organization_id, :workspace_id, :project_id, "
                ":script_run_id, :brief_id, :brief_version_id, :concept_run_id, :candidate_id, "
                ":selection_id, 1, '1.0.0', CAST(:content AS jsonb), :script_digest, :now)"
            ),
            values | {"content": json.dumps({"script": key})},
        )
    return ScriptGraph(
        seed=seed,
        concept_run_id=concept_run_id,
        concept_candidate_id=candidate_id,
        concept_selection_id=selection_id,
        script_run_id=script_run_id,
        script_version_id=script_version_id,
        script_content_digest=script_digest,
    )


def _storyboard_run(graph: ScriptGraph, *, run_id: UUID | None = None) -> StoryboardRun:
    now = datetime.now(UTC)
    return StoryboardRun(
        id=run_id or uuid4(),
        organization_id=graph.seed.context.organization_id,
        workspace_id=graph.seed.context.workspace_id,
        project_id=graph.seed.project_id,
        brief_id=graph.seed.brief_id,
        brief_version_id=graph.seed.brief_version_id,
        concept_run_id=graph.concept_run_id,
        concept_candidate_id=graph.concept_candidate_id,
        concept_selection_id=graph.concept_selection_id,
        script_run_id=graph.script_run_id,
        script_version_id=graph.script_version_id,
        script_content_digest=graph.script_content_digest,
        instruction_template_id="storyboard-template",
        instruction_template_version="1",
        provider_id="offline",
        model_id="fake",
        status=CreativeRunStatus.COMPLETED,
        failure_category=None,
        created_by_actor_subject=graph.seed.context.actor_subject,
        created_at=now,
        completed_at=now,
        version=1,
    )


def _storyboard_version(run: StoryboardRun, *, version_id: UUID | None = None) -> StoryboardVersion:
    return StoryboardVersion(
        id=version_id or uuid4(),
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        storyboard_run_id=run.id,
        brief_id=run.brief_id,
        brief_version_id=run.brief_version_id,
        concept_run_id=run.concept_run_id,
        concept_candidate_id=run.concept_candidate_id,
        concept_selection_id=run.concept_selection_id,
        script_run_id=run.script_run_id,
        script_version_id=run.script_version_id,
        version_number=1,
        schema_version="1.0.0",
        content={"scenes": [{"id": "scene-1"}]},
        content_digest=_digest(f"storyboard-{run.id}"),
        total_duration_seconds=30,
        scene_count=1,
        created_at=datetime.now(UTC),
    )


def _shot_plan_run(storyboard: StoryboardGraph, *, run_id: UUID | None = None) -> ShotPlanRun:
    now = datetime.now(UTC)
    graph = storyboard.script
    return ShotPlanRun(
        id=run_id or uuid4(),
        organization_id=graph.seed.context.organization_id,
        workspace_id=graph.seed.context.workspace_id,
        project_id=graph.seed.project_id,
        storyboard_run_id=storyboard.run_id,
        storyboard_version_id=storyboard.version_id,
        script_run_id=graph.script_run_id,
        script_version_id=graph.script_version_id,
        brief_id=graph.seed.brief_id,
        brief_version_id=graph.seed.brief_version_id,
        concept_run_id=graph.concept_run_id,
        concept_candidate_id=graph.concept_candidate_id,
        concept_selection_id=graph.concept_selection_id,
        storyboard_content_digest=storyboard.content_digest,
        instruction_template_id="shot-template",
        instruction_template_version="1",
        provider_id="offline",
        model_id="fake",
        status=CreativeRunStatus.COMPLETED,
        failure_category=None,
        created_by_actor_subject=graph.seed.context.actor_subject,
        created_at=now,
        completed_at=now,
        version=1,
    )


def _shot_plan_version(run: ShotPlanRun, *, version_id: UUID | None = None) -> ShotPlanVersion:
    return ShotPlanVersion(
        id=version_id or uuid4(),
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        shot_plan_run_id=run.id,
        storyboard_run_id=run.storyboard_run_id,
        storyboard_version_id=run.storyboard_version_id,
        script_run_id=run.script_run_id,
        script_version_id=run.script_version_id,
        brief_id=run.brief_id,
        brief_version_id=run.brief_version_id,
        concept_run_id=run.concept_run_id,
        concept_candidate_id=run.concept_candidate_id,
        concept_selection_id=run.concept_selection_id,
        version_number=1,
        schema_version="1.0.0",
        content={"shots": [{"id": "shot-1"}]},
        content_digest=_digest(f"shot-plan-{run.id}"),
        total_duration_seconds=30,
        scene_count=1,
        shot_count=1,
        created_at=datetime.now(UTC),
    )


def _insert_storyboard(engine: Engine, graph: ScriptGraph) -> StoryboardGraph:
    run = _storyboard_run(graph)
    version = _storyboard_version(run)
    with engine.begin() as connection:
        _insert_storyboard_rows(connection, run, version)
    return StoryboardGraph(graph, run.id, version.id, version.content_digest)


def _insert_storyboard_rows(
    connection: Connection, run: StoryboardRun, version: StoryboardVersion
) -> None:
    connection.execute(
        text(
            "INSERT INTO storyboard_runs "
            "(id, organization_id, workspace_id, project_id, brief_id, brief_version_id, "
            "concept_run_id, concept_candidate_id, concept_selection_id, script_run_id, "
            "script_version_id, script_content_digest, instruction_template_id, "
            "instruction_template_version, provider_id, model_id, status, failure_category, "
            "created_by_actor_subject, created_at, completed_at, version) VALUES "
            "(:id, :organization_id, :workspace_id, :project_id, :brief_id, "
            ":brief_version_id, :concept_run_id, :concept_candidate_id, "
            ":concept_selection_id, :script_run_id, :script_version_id, "
            ":script_content_digest, :instruction_template_id, :instruction_template_version, "
            ":provider_id, :model_id, :status, :failure_category, :created_by_actor_subject, "
            ":created_at, :completed_at, :version)"
        ),
        _run_values(run),
    )
    connection.execute(
        text(
            "INSERT INTO storyboard_versions "
            "(id, organization_id, workspace_id, project_id, storyboard_run_id, brief_id, "
            "brief_version_id, concept_run_id, concept_candidate_id, concept_selection_id, "
            "script_run_id, script_version_id, version_number, schema_version, content, "
            "content_digest, total_duration_seconds, scene_count, created_at) VALUES "
            "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, "
            ":brief_id, :brief_version_id, :concept_run_id, :concept_candidate_id, "
            ":concept_selection_id, :script_run_id, :script_version_id, :version_number, "
            ":schema_version, CAST(:content AS jsonb), :content_digest, "
            ":total_duration_seconds, :scene_count, :created_at)"
        ),
        _storyboard_version_values(version),
    )


def _insert_shot_plan(engine: Engine, storyboard: StoryboardGraph) -> ShotPlanGraph:
    run = _shot_plan_run(storyboard)
    version = _shot_plan_version(run)
    with engine.begin() as connection:
        _insert_shot_plan_rows(connection, run, version)
    return ShotPlanGraph(storyboard, run.id, version.id, version.content_digest)


def _insert_shot_plan_rows(
    connection: Connection, run: ShotPlanRun, version: ShotPlanVersion
) -> None:
    connection.execute(
        text(
            "INSERT INTO shot_plan_runs "
            "(id, organization_id, workspace_id, project_id, storyboard_run_id, "
            "storyboard_version_id, script_run_id, script_version_id, brief_id, "
            "brief_version_id, concept_run_id, concept_candidate_id, concept_selection_id, "
            "storyboard_content_digest, instruction_template_id, instruction_template_version, "
            "provider_id, model_id, status, failure_category, created_by_actor_subject, "
            "created_at, completed_at, version) VALUES "
            "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, "
            ":storyboard_version_id, :script_run_id, :script_version_id, :brief_id, "
            ":brief_version_id, :concept_run_id, :concept_candidate_id, "
            ":concept_selection_id, :storyboard_content_digest, :instruction_template_id, "
            ":instruction_template_version, :provider_id, :model_id, :status, "
            ":failure_category, :created_by_actor_subject, :created_at, :completed_at, :version)"
        ),
        _shot_run_values(run),
    )
    connection.execute(
        text(
            "INSERT INTO shot_plan_versions "
            "(id, organization_id, workspace_id, project_id, shot_plan_run_id, "
            "storyboard_run_id, storyboard_version_id, script_run_id, script_version_id, "
            "brief_id, brief_version_id, concept_run_id, concept_candidate_id, "
            "concept_selection_id, version_number, schema_version, content, content_digest, "
            "total_duration_seconds, scene_count, shot_count, created_at) VALUES "
            "(:id, :organization_id, :workspace_id, :project_id, :shot_plan_run_id, "
            ":storyboard_run_id, :storyboard_version_id, :script_run_id, :script_version_id, "
            ":brief_id, :brief_version_id, :concept_run_id, :concept_candidate_id, "
            ":concept_selection_id, :version_number, :schema_version, CAST(:content AS jsonb), "
            ":content_digest, :total_duration_seconds, :scene_count, :shot_count, :created_at)"
        ),
        _shot_version_values(version),
    )


def _run_values(run: StoryboardRun) -> dict[str, object]:
    return {
        "id": run.id,
        "organization_id": run.organization_id,
        "workspace_id": run.workspace_id,
        "project_id": run.project_id,
        "brief_id": run.brief_id,
        "brief_version_id": run.brief_version_id,
        "concept_run_id": run.concept_run_id,
        "concept_candidate_id": run.concept_candidate_id,
        "concept_selection_id": run.concept_selection_id,
        "script_run_id": run.script_run_id,
        "script_version_id": run.script_version_id,
        "script_content_digest": run.script_content_digest,
        "instruction_template_id": run.instruction_template_id,
        "instruction_template_version": run.instruction_template_version,
        "provider_id": run.provider_id,
        "model_id": run.model_id,
        "status": run.status.value,
        "failure_category": run.failure_category,
        "created_by_actor_subject": run.created_by_actor_subject,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "version": run.version,
    }


def _storyboard_version_values(version: StoryboardVersion) -> dict[str, object]:
    return {
        "id": version.id,
        "organization_id": version.organization_id,
        "workspace_id": version.workspace_id,
        "project_id": version.project_id,
        "storyboard_run_id": version.storyboard_run_id,
        "brief_id": version.brief_id,
        "brief_version_id": version.brief_version_id,
        "concept_run_id": version.concept_run_id,
        "concept_candidate_id": version.concept_candidate_id,
        "concept_selection_id": version.concept_selection_id,
        "script_run_id": version.script_run_id,
        "script_version_id": version.script_version_id,
        "version_number": version.version_number,
        "schema_version": version.schema_version,
        "content": json.dumps(version.content),
        "content_digest": version.content_digest,
        "total_duration_seconds": version.total_duration_seconds,
        "scene_count": version.scene_count,
        "created_at": version.created_at,
    }


def _shot_run_values(run: ShotPlanRun) -> dict[str, object]:
    return {
        "id": run.id,
        "organization_id": run.organization_id,
        "workspace_id": run.workspace_id,
        "project_id": run.project_id,
        "storyboard_run_id": run.storyboard_run_id,
        "storyboard_version_id": run.storyboard_version_id,
        "script_run_id": run.script_run_id,
        "script_version_id": run.script_version_id,
        "brief_id": run.brief_id,
        "brief_version_id": run.brief_version_id,
        "concept_run_id": run.concept_run_id,
        "concept_candidate_id": run.concept_candidate_id,
        "concept_selection_id": run.concept_selection_id,
        "storyboard_content_digest": run.storyboard_content_digest,
        "instruction_template_id": run.instruction_template_id,
        "instruction_template_version": run.instruction_template_version,
        "provider_id": run.provider_id,
        "model_id": run.model_id,
        "status": run.status.value,
        "failure_category": run.failure_category,
        "created_by_actor_subject": run.created_by_actor_subject,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "version": run.version,
    }


def _shot_version_values(version: ShotPlanVersion) -> dict[str, object]:
    return {
        "id": version.id,
        "organization_id": version.organization_id,
        "workspace_id": version.workspace_id,
        "project_id": version.project_id,
        "shot_plan_run_id": version.shot_plan_run_id,
        "storyboard_run_id": version.storyboard_run_id,
        "storyboard_version_id": version.storyboard_version_id,
        "script_run_id": version.script_run_id,
        "script_version_id": version.script_version_id,
        "brief_id": version.brief_id,
        "brief_version_id": version.brief_version_id,
        "concept_run_id": version.concept_run_id,
        "concept_candidate_id": version.concept_candidate_id,
        "concept_selection_id": version.concept_selection_id,
        "version_number": version.version_number,
        "schema_version": version.schema_version,
        "content": json.dumps(version.content),
        "content_digest": version.content_digest,
        "total_duration_seconds": version.total_duration_seconds,
        "scene_count": version.scene_count,
        "shot_count": version.shot_count,
        "created_at": version.created_at,
    }


def _assert_integrity_error(engine: Engine, sql: str, values: dict[str, object]) -> None:
    with pytest.raises((DataError, IntegrityError)), engine.begin() as connection:
        connection.execute(text(sql), values)


def _operation(
    seed: ProjectSeed,
    operation: VisualPlanningOperationType,
    key: str,
    digest: str | None = None,
) -> VisualPlanningOperation:
    return VisualPlanningOperation(
        id=uuid4(),
        organization_id=seed.context.organization_id,
        workspace_id=seed.context.workspace_id,
        project_id=seed.project_id,
        operation=operation,
        idempotency_key=key,
        request_digest=digest or _digest(key),
        status=VisualPlanningOperationStatus.RESERVED,
        outcome_storyboard_run_id=None,
        outcome_storyboard_version_id=None,
        outcome_shot_plan_run_id=None,
        outcome_shot_plan_version_id=None,
        submitted_by_actor_subject=seed.context.actor_subject,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        correlation_id=seed.context.correlation_id,
        version=1,
    )


def _accepted_storyboard(
    operation: VisualPlanningOperation, storyboard: StoryboardGraph
) -> VisualPlanningOperation:
    return replace(
        operation,
        status=VisualPlanningOperationStatus.ACCEPTED,
        outcome_storyboard_run_id=storyboard.run_id,
        outcome_storyboard_version_id=storyboard.version_id,
        completed_at=datetime.now(UTC),
        version=operation.version + 1,
    )


def _accepted_shot(
    operation: VisualPlanningOperation, shot: ShotPlanGraph
) -> VisualPlanningOperation:
    return replace(
        operation,
        status=VisualPlanningOperationStatus.ACCEPTED,
        outcome_shot_plan_run_id=shot.run_id,
        outcome_shot_plan_version_id=shot.version_id,
        completed_at=datetime.now(UTC),
        version=operation.version + 1,
    )


def _operation_values(operation: VisualPlanningOperation) -> dict[str, object]:
    return {
        "id": operation.id,
        "organization_id": operation.organization_id,
        "workspace_id": operation.workspace_id,
        "project_id": operation.project_id,
        "operation": operation.operation.value,
        "idempotency_key": operation.idempotency_key,
        "request_digest": operation.request_digest,
        "status": operation.status.value,
        "outcome_storyboard_run_id": operation.outcome_storyboard_run_id,
        "outcome_storyboard_version_id": operation.outcome_storyboard_version_id,
        "outcome_shot_plan_run_id": operation.outcome_shot_plan_run_id,
        "outcome_shot_plan_version_id": operation.outcome_shot_plan_version_id,
        "submitted_by_actor_subject": operation.submitted_by_actor_subject,
        "submitted_at": operation.submitted_at,
        "completed_at": operation.completed_at,
        "correlation_id": operation.correlation_id,
        "version": operation.version,
    }


VISUAL_OPERATION_INSERT = (
    "INSERT INTO visual_planning_operations "
    "(id, organization_id, workspace_id, project_id, operation, idempotency_key, "
    "request_digest, status, outcome_storyboard_run_id, outcome_storyboard_version_id, "
    "outcome_shot_plan_run_id, outcome_shot_plan_version_id, submitted_by_actor_subject, "
    "submitted_at, completed_at, correlation_id, version) VALUES "
    "(:id, :organization_id, :workspace_id, :project_id, :operation, :idempotency_key, "
    ":request_digest, :status, :outcome_storyboard_run_id, :outcome_storyboard_version_id, "
    ":outcome_shot_plan_run_id, :outcome_shot_plan_version_id, :submitted_by_actor_subject, "
    ":submitted_at, :completed_at, :correlation_id, :version)"
)


def _insert_operation(engine: Engine, operation: VisualPlanningOperation) -> None:
    with engine.begin() as connection:
        connection.execute(text(VISUAL_OPERATION_INSERT), _operation_values(operation))


@pytest.mark.parametrize("bad_digest", ["a" * 63, "a" * 65, "A" * 64, "g" * 64])
def test_visual_operation_rejects_invalid_digest(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    bad_digest: str,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    operation = _operation(
        seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "bad-digest", bad_digest
    )
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, _operation_values(operation))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operation", "render_storyboard"),
        ("status", "done"),
        ("version", 0),
    ],
)
def test_visual_operation_rejects_invalid_enum_and_version(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    field: str,
    value: object,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    values = _operation_values(
        _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, field)
    )
    values[field] = value
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, values)


@pytest.mark.parametrize(
    "outcome_field",
    [
        "outcome_storyboard_run_id",
        "outcome_storyboard_version_id",
        "outcome_shot_plan_run_id",
        "outcome_shot_plan_version_id",
    ],
)
def test_reserved_visual_operation_rejects_any_outcome_or_completion(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    outcome_field: str,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    values = _operation_values(
        _operation(
            seed, VisualPlanningOperationType.GENERATE_STORYBOARD, f"reserved-{outcome_field}"
        )
    )
    values[outcome_field] = uuid4()
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, values)
    values = _operation_values(
        _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "reserved-time")
    )
    values["completed_at"] = datetime.now(UTC)
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, values)


def test_visual_operation_direct_uniqueness_scope_and_valid_outcomes(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    other_seed = _seed_project(persistence_session_factory, name="Other")
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "a")
    )
    shot = _insert_shot_plan(database_engine, storyboard)

    reserved = _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "same-key")
    _insert_operation(database_engine, reserved)
    _assert_integrity_error(
        database_engine,
        VISUAL_OPERATION_INSERT,
        _operation_values(replace(reserved, id=uuid4())),
    )
    _insert_operation(
        database_engine,
        _operation(seed, VisualPlanningOperationType.GENERATE_SHOT_PLAN, "same-key"),
    )
    _insert_operation(
        database_engine,
        _operation(other_seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "same-key"),
    )
    _insert_operation(
        database_engine,
        _accepted_storyboard(
            _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "accepted-board"),
            storyboard,
        ),
    )
    _insert_operation(
        database_engine,
        _accepted_shot(
            _operation(seed, VisualPlanningOperationType.GENERATE_SHOT_PLAN, "accepted-shot"), shot
        ),
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda op, board, shot: replace(
            op, status=VisualPlanningOperationStatus.ACCEPTED, completed_at=datetime.now(UTC)
        ),
        lambda op, board, shot: replace(
            op,
            status=VisualPlanningOperationStatus.ACCEPTED,
            outcome_storyboard_run_id=board.run_id,
            completed_at=datetime.now(UTC),
        ),
        lambda op, board, shot: replace(
            op,
            status=VisualPlanningOperationStatus.ACCEPTED,
            outcome_storyboard_version_id=board.version_id,
            completed_at=datetime.now(UTC),
        ),
        lambda op, board, shot: replace(
            _accepted_storyboard(op, board), outcome_shot_plan_run_id=shot.run_id
        ),
        lambda op, board, shot: replace(_accepted_storyboard(op, board), completed_at=None),
    ],
)
def test_accepted_storyboard_operation_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    mutator: Callable[
        [VisualPlanningOperation, StoryboardGraph, ShotPlanGraph], VisualPlanningOperation
    ],
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "board")
    )
    shot = _insert_shot_plan(database_engine, storyboard)
    op = _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "bad-board-accepted")
    bad = mutator(op, storyboard, shot)
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, _operation_values(bad))


@pytest.mark.parametrize(
    "mutator",
    [
        lambda op, board, shot: replace(
            op, status=VisualPlanningOperationStatus.ACCEPTED, completed_at=datetime.now(UTC)
        ),
        lambda op, board, shot: replace(
            op,
            status=VisualPlanningOperationStatus.ACCEPTED,
            outcome_shot_plan_run_id=shot.run_id,
            completed_at=datetime.now(UTC),
        ),
        lambda op, board, shot: replace(
            op,
            status=VisualPlanningOperationStatus.ACCEPTED,
            outcome_shot_plan_version_id=shot.version_id,
            completed_at=datetime.now(UTC),
        ),
        lambda op, board, shot: replace(
            _accepted_shot(op, shot), outcome_storyboard_run_id=board.run_id
        ),
        lambda op, board, shot: replace(_accepted_shot(op, shot), completed_at=None),
    ],
)
def test_accepted_shot_plan_operation_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    mutator: Callable[
        [VisualPlanningOperation, StoryboardGraph, ShotPlanGraph], VisualPlanningOperation
    ],
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "shot")
    )
    shot = _insert_shot_plan(database_engine, storyboard)
    op = _operation(seed, VisualPlanningOperationType.GENERATE_SHOT_PLAN, "bad-shot-accepted")
    bad = mutator(op, storyboard, shot)
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, _operation_values(bad))


@pytest.mark.parametrize("wrong_field", ["organization_id", "workspace_id", "project_id"])
@pytest.mark.parametrize(
    "outcome_pair",
    [
        ("outcome_storyboard_run_id", "run_id"),
        ("outcome_storyboard_version_id", "version_id"),
    ],
)
def test_visual_operation_rejects_cross_scope_storyboard_outcomes(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    wrong_field: str,
    outcome_pair: tuple[str, str],
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    other = _seed_project(persistence_session_factory, name="Other")
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "scope")
    )
    values = _operation_values(
        _accepted_storyboard(
            _operation(
                seed,
                VisualPlanningOperationType.GENERATE_STORYBOARD,
                f"{wrong_field}-{outcome_pair[0]}",
            ),
            storyboard,
        )
    )
    values[wrong_field] = getattr(other.context, wrong_field, other.project_id)
    values[outcome_pair[0]] = getattr(storyboard, outcome_pair[1])
    _assert_integrity_error(database_engine, VISUAL_OPERATION_INSERT, values)


def test_storyboard_lineage_constraints_reject_same_project_mismatches(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    first = _insert_script_graph(database_engine, seed, "first")
    second = _insert_script_graph(database_engine, seed, "second")
    bad_run = replace(_storyboard_run(first), script_version_id=second.script_version_id)
    _assert_integrity_error(
        database_engine,
        "INSERT INTO storyboard_runs "
        "(id, organization_id, workspace_id, project_id, brief_id, brief_version_id, "
        "concept_run_id, concept_candidate_id, concept_selection_id, script_run_id, "
        "script_version_id, script_content_digest, instruction_template_id, "
        "instruction_template_version, provider_id, model_id, status, failure_category, "
        "created_by_actor_subject, created_at, completed_at, version) VALUES "
        "(:id, :organization_id, :workspace_id, :project_id, :brief_id, :brief_version_id, "
        ":concept_run_id, :concept_candidate_id, :concept_selection_id, :script_run_id, "
        ":script_version_id, :script_content_digest, :instruction_template_id, "
        ":instruction_template_version, :provider_id, :model_id, :status, :failure_category, "
        ":created_by_actor_subject, :created_at, :completed_at, :version)",
        _run_values(bad_run),
    )
    valid_run = _storyboard_run(first)
    valid_version = _storyboard_version(valid_run)
    with database_engine.begin() as connection:
        _insert_storyboard_rows(connection, valid_run, valid_version)
    bad_version = replace(valid_version, id=uuid4(), script_version_id=second.script_version_id)
    _assert_integrity_error(
        database_engine,
        "INSERT INTO storyboard_versions "
        "(id, organization_id, workspace_id, project_id, storyboard_run_id, brief_id, "
        "brief_version_id, concept_run_id, concept_candidate_id, concept_selection_id, "
        "script_run_id, script_version_id, version_number, schema_version, content, "
        "content_digest, total_duration_seconds, scene_count, created_at) VALUES "
        "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, :brief_id, "
        ":brief_version_id, :concept_run_id, :concept_candidate_id, :concept_selection_id, "
        ":script_run_id, :script_version_id, :version_number, :schema_version, "
        "CAST(:content AS jsonb), :content_digest, :total_duration_seconds, :scene_count, "
        ":created_at)",
        _storyboard_version_values(bad_version),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("script_content_digest", "A" * 64),
        ("status", "waiting"),
        ("failure_category", "unknown"),
        ("version", 0),
    ],
)
def test_storyboard_run_artifact_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    field: str,
    value: object,
) -> None:
    del clean_database
    graph = _insert_script_graph(database_engine, _seed_project(persistence_session_factory), field)
    values = _run_values(_storyboard_run(graph))
    values[field] = value
    _assert_integrity_error(
        database_engine,
        "INSERT INTO storyboard_runs "
        "(id, organization_id, workspace_id, project_id, brief_id, brief_version_id, "
        "concept_run_id, concept_candidate_id, concept_selection_id, script_run_id, "
        "script_version_id, script_content_digest, instruction_template_id, "
        "instruction_template_version, provider_id, model_id, status, failure_category, "
        "created_by_actor_subject, created_at, completed_at, version) VALUES "
        "(:id, :organization_id, :workspace_id, :project_id, :brief_id, :brief_version_id, "
        ":concept_run_id, :concept_candidate_id, :concept_selection_id, :script_run_id, "
        ":script_version_id, :script_content_digest, :instruction_template_id, "
        ":instruction_template_version, :provider_id, :model_id, :status, :failure_category, "
        ":created_by_actor_subject, :created_at, :completed_at, :version)",
        values,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_digest", "z" * 64),
        ("version_number", 0),
        ("total_duration_seconds", 0),
        ("scene_count", 0),
        ("scene_count", 61),
    ],
)
def test_storyboard_version_artifact_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    field: str,
    value: object,
) -> None:
    del clean_database
    run = _storyboard_run(
        _insert_script_graph(database_engine, _seed_project(persistence_session_factory), field)
    )
    version = _storyboard_version(run)
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO storyboard_runs "
                "(id, organization_id, workspace_id, project_id, brief_id, brief_version_id, "
                "concept_run_id, concept_candidate_id, concept_selection_id, script_run_id, "
                "script_version_id, script_content_digest, instruction_template_id, "
                "instruction_template_version, provider_id, model_id, status, failure_category, "
                "created_by_actor_subject, created_at, completed_at, version) VALUES "
                "(:id, :organization_id, :workspace_id, :project_id, :brief_id, "
                ":brief_version_id, :concept_run_id, :concept_candidate_id, "
                ":concept_selection_id, :script_run_id, :script_version_id, "
                ":script_content_digest, :instruction_template_id, :instruction_template_version, "
                ":provider_id, :model_id, :status, :failure_category, :created_by_actor_subject, "
                ":created_at, :completed_at, :version)"
            ),
            _run_values(run),
        )
    values = _storyboard_version_values(version)
    values[field] = value
    _assert_integrity_error(
        database_engine,
        "INSERT INTO storyboard_versions "
        "(id, organization_id, workspace_id, project_id, storyboard_run_id, brief_id, "
        "brief_version_id, concept_run_id, concept_candidate_id, concept_selection_id, "
        "script_run_id, script_version_id, version_number, schema_version, content, "
        "content_digest, total_duration_seconds, scene_count, created_at) VALUES "
        "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, :brief_id, "
        ":brief_version_id, :concept_run_id, :concept_candidate_id, :concept_selection_id, "
        ":script_run_id, :script_version_id, :version_number, :schema_version, "
        "CAST(:content AS jsonb), :content_digest, :total_duration_seconds, :scene_count, "
        ":created_at)",
        values,
    )


def test_shot_plan_lineage_constraints_reject_same_project_mismatches(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    storyboard_a = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "a")
    )
    storyboard_b = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "b")
    )
    bad_run = replace(
        _shot_plan_run(storyboard_a),
        storyboard_version_id=storyboard_b.version_id,
    )
    _assert_integrity_error(
        database_engine,
        "INSERT INTO shot_plan_runs "
        "(id, organization_id, workspace_id, project_id, storyboard_run_id, "
        "storyboard_version_id, script_run_id, script_version_id, brief_id, brief_version_id, "
        "concept_run_id, concept_candidate_id, concept_selection_id, storyboard_content_digest, "
        "instruction_template_id, instruction_template_version, provider_id, model_id, status, "
        "failure_category, created_by_actor_subject, created_at, completed_at, version) VALUES "
        "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, "
        ":storyboard_version_id, :script_run_id, :script_version_id, :brief_id, "
        ":brief_version_id, :concept_run_id, :concept_candidate_id, :concept_selection_id, "
        ":storyboard_content_digest, :instruction_template_id, :instruction_template_version, "
        ":provider_id, :model_id, :status, :failure_category, :created_by_actor_subject, "
        ":created_at, :completed_at, :version)",
        _shot_run_values(bad_run),
    )
    valid_run = _shot_plan_run(storyboard_a)
    valid_version = _shot_plan_version(valid_run)
    with database_engine.begin() as connection:
        _insert_shot_plan_rows(connection, valid_run, valid_version)
    bad_version = replace(valid_version, id=uuid4(), storyboard_version_id=storyboard_b.version_id)
    _assert_integrity_error(
        database_engine,
        "INSERT INTO shot_plan_versions "
        "(id, organization_id, workspace_id, project_id, shot_plan_run_id, storyboard_run_id, "
        "storyboard_version_id, script_run_id, script_version_id, brief_id, brief_version_id, "
        "concept_run_id, concept_candidate_id, concept_selection_id, version_number, "
        "schema_version, content, content_digest, total_duration_seconds, scene_count, "
        "shot_count, created_at) VALUES (:id, :organization_id, :workspace_id, :project_id, "
        ":shot_plan_run_id, :storyboard_run_id, :storyboard_version_id, :script_run_id, "
        ":script_version_id, :brief_id, :brief_version_id, :concept_run_id, "
        ":concept_candidate_id, :concept_selection_id, :version_number, :schema_version, "
        "CAST(:content AS jsonb), :content_digest, :total_duration_seconds, :scene_count, "
        ":shot_count, :created_at)",
        _shot_version_values(bad_version),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("storyboard_content_digest", "A" * 64),
        ("status", "waiting"),
        ("failure_category", "unknown"),
        ("version", 0),
    ],
)
def test_shot_plan_run_artifact_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    field: str,
    value: object,
) -> None:
    del clean_database
    storyboard = _insert_storyboard(
        database_engine,
        _insert_script_graph(database_engine, _seed_project(persistence_session_factory), field),
    )
    values = _shot_run_values(_shot_plan_run(storyboard))
    values[field] = value
    _assert_integrity_error(
        database_engine,
        "INSERT INTO shot_plan_runs "
        "(id, organization_id, workspace_id, project_id, storyboard_run_id, "
        "storyboard_version_id, script_run_id, script_version_id, brief_id, brief_version_id, "
        "concept_run_id, concept_candidate_id, concept_selection_id, storyboard_content_digest, "
        "instruction_template_id, instruction_template_version, provider_id, model_id, status, "
        "failure_category, created_by_actor_subject, created_at, completed_at, version) VALUES "
        "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, "
        ":storyboard_version_id, :script_run_id, :script_version_id, :brief_id, "
        ":brief_version_id, :concept_run_id, :concept_candidate_id, :concept_selection_id, "
        ":storyboard_content_digest, :instruction_template_id, :instruction_template_version, "
        ":provider_id, :model_id, :status, :failure_category, :created_by_actor_subject, "
        ":created_at, :completed_at, :version)",
        values,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_digest", "z" * 64),
        ("version_number", 0),
        ("total_duration_seconds", 0),
        ("scene_count", 0),
        ("scene_count", 61),
        ("shot_count", 0),
        ("shot_count", 181),
    ],
)
def test_shot_plan_version_artifact_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    field: str,
    value: object,
) -> None:
    del clean_database
    storyboard = _insert_storyboard(
        database_engine,
        _insert_script_graph(database_engine, _seed_project(persistence_session_factory), field),
    )
    run = _shot_plan_run(storyboard)
    version = _shot_plan_version(run)
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO shot_plan_runs "
                "(id, organization_id, workspace_id, project_id, storyboard_run_id, "
                "storyboard_version_id, script_run_id, script_version_id, brief_id, "
                "brief_version_id, concept_run_id, concept_candidate_id, concept_selection_id, "
                "storyboard_content_digest, instruction_template_id, instruction_template_version, "
                "provider_id, model_id, status, failure_category, created_by_actor_subject, "
                "created_at, completed_at, version) VALUES "
                "(:id, :organization_id, :workspace_id, :project_id, :storyboard_run_id, "
                ":storyboard_version_id, :script_run_id, :script_version_id, :brief_id, "
                ":brief_version_id, :concept_run_id, :concept_candidate_id, "
                ":concept_selection_id, :storyboard_content_digest, :instruction_template_id, "
                ":instruction_template_version, :provider_id, :model_id, :status, "
                ":failure_category, :created_by_actor_subject, :created_at, "
                ":completed_at, :version)"
            ),
            _shot_run_values(run),
        )
    values = _shot_version_values(version)
    values[field] = value
    _assert_integrity_error(
        database_engine,
        "INSERT INTO shot_plan_versions "
        "(id, organization_id, workspace_id, project_id, shot_plan_run_id, storyboard_run_id, "
        "storyboard_version_id, script_run_id, script_version_id, brief_id, brief_version_id, "
        "concept_run_id, concept_candidate_id, concept_selection_id, version_number, "
        "schema_version, content, content_digest, total_duration_seconds, scene_count, "
        "shot_count, created_at) VALUES (:id, :organization_id, :workspace_id, :project_id, "
        ":shot_plan_run_id, :storyboard_run_id, :storyboard_version_id, :script_run_id, "
        ":script_version_id, :brief_id, :brief_version_id, :concept_run_id, "
        ":concept_candidate_id, :concept_selection_id, :version_number, :schema_version, "
        "CAST(:content AS jsonb), :content_digest, :total_duration_seconds, :scene_count, "
        ":shot_count, :created_at)",
        values,
    )


def test_visual_planning_repositories_are_scoped_and_read_only(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    graph = _insert_script_graph(database_engine, seed, "repo")
    storyboard = _insert_storyboard(database_engine, graph)
    shot = _insert_shot_plan(database_engine, storyboard)
    with SqlAlchemyUnitOfWork(persistence_session_factory) as uow:
        assert (
            uow.storyboard_runs.get(
                seed.context.organization_id,
                seed.context.workspace_id,
                seed.project_id,
                storyboard.run_id,
            )
            is not None
        )
        assert (
            uow.storyboard_runs.get(
                uuid4(), seed.context.workspace_id, seed.project_id, storyboard.run_id
            )
            is None
        )
        assert (
            uow.storyboard_versions.get_for_run(
                seed.context.organization_id,
                seed.context.workspace_id,
                seed.project_id,
                storyboard.run_id,
                1,
            )
            is not None
        )
        assert (
            uow.shot_plan_runs.get(
                seed.context.organization_id,
                seed.context.workspace_id,
                seed.project_id,
                shot.run_id,
            )
            is not None
        )
        assert (
            uow.shot_plan_versions.get_for_run(
                seed.context.organization_id,
                seed.context.workspace_id,
                seed.project_id,
                shot.run_id,
                1,
            )
            is not None
        )
        assert (
            uow.visual_planning_operations.get_by_key(
                seed.context.organization_id,
                seed.context.workspace_id,
                seed.project_id,
                VisualPlanningOperationType.GENERATE_STORYBOARD,
                "missing",
            )
            is None
        )
    assert not hasattr(SqlAlchemyUnitOfWork, "commit") or callable(SqlAlchemyUnitOfWork.commit)
    assert not hasattr(type(uow.storyboard_versions), "update")
    assert not hasattr(type(uow.shot_plan_versions), "update")


def test_reserve_and_finalize_storyboard_cas(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "cas-board")
    )
    operation = _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "cas-board")
    with SqlAlchemyUnitOfWork(persistence_session_factory) as uow:
        reserved = uow.visual_planning_operations.reserve(operation)
        assert reserved is not None
        assert uow.visual_planning_operations.reserve(replace(operation, id=uuid4())) is None
        existing = uow.visual_planning_operations.get_by_key(
            seed.context.organization_id,
            seed.context.workspace_id,
            seed.project_id,
            VisualPlanningOperationType.GENERATE_STORYBOARD,
            "cas-board",
        )
        assert existing is not None and existing.request_digest == operation.request_digest
        accepted = uow.visual_planning_operations.finalize_accepted(
            _accepted_storyboard(reserved, storyboard), expected_version=1
        )
        assert accepted.status is VisualPlanningOperationStatus.ACCEPTED
        assert accepted.version == 2
        assert accepted.outcome_storyboard_run_id == storyboard.run_id
        assert accepted.outcome_shot_plan_run_id is None
        with pytest.raises(VersionConflict):
            uow.visual_planning_operations.finalize_accepted(
                _accepted_storyboard(reserved, storyboard), expected_version=1
            )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda op: replace(op, organization_id=uuid4()),
        lambda op: replace(op, workspace_id=uuid4()),
        lambda op: replace(op, project_id=uuid4()),
        lambda op: replace(op, operation=VisualPlanningOperationType.GENERATE_SHOT_PLAN),
        lambda op: replace(op, idempotency_key="wrong"),
        lambda op: replace(op, request_digest="b" * 64),
    ],
)
def test_finalize_rejects_wrong_scope_key_digest_and_version(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    mutator: Callable[[VisualPlanningOperation], VisualPlanningOperation],
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "cas-bad")
    )
    operation = _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "cas-bad")
    with SqlAlchemyUnitOfWork(persistence_session_factory) as uow:
        reserved = uow.visual_planning_operations.reserve(operation)
        assert reserved is not None
        with pytest.raises(VersionConflict):
            uow.visual_planning_operations.finalize_accepted(
                _accepted_storyboard(mutator(reserved), storyboard), expected_version=1
            )
        with pytest.raises(VersionConflict):
            uow.visual_planning_operations.finalize_accepted(
                _accepted_storyboard(reserved, storyboard), expected_version=99
            )


def test_reserve_and_finalize_shot_plan_cas(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    shot = _insert_shot_plan(
        database_engine,
        _insert_storyboard(
            database_engine, _insert_script_graph(database_engine, seed, "cas-shot")
        ),
    )
    operation = _operation(seed, VisualPlanningOperationType.GENERATE_SHOT_PLAN, "cas-shot")
    with SqlAlchemyUnitOfWork(persistence_session_factory) as uow:
        reserved = uow.visual_planning_operations.reserve(operation)
        assert reserved is not None
        accepted = uow.visual_planning_operations.finalize_accepted(
            _accepted_shot(reserved, shot), expected_version=1
        )
        assert accepted.status is VisualPlanningOperationStatus.ACCEPTED
        assert accepted.outcome_shot_plan_run_id == shot.run_id
        assert accepted.outcome_storyboard_run_id is None
        with pytest.raises(VersionConflict):
            uow.visual_planning_operations.finalize_accepted(
                _accepted_shot(reserved, shot), expected_version=1
            )


@pytest.mark.parametrize(
    "operation_type",
    [
        VisualPlanningOperationType.GENERATE_STORYBOARD,
        VisualPlanningOperationType.GENERATE_SHOT_PLAN,
    ],
)
@pytest.mark.parametrize("changed_digest", [False, True])
def test_concurrent_same_key_reserve_creates_one_operation(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    operation_type: VisualPlanningOperationType,
    changed_digest: bool,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    winner_ready, loser_started = Event(), Event()
    key = f"concurrent-{operation_type.value}-{changed_digest}"
    digest = _digest(key)
    loser_digest = _digest(f"{key}-loser") if changed_digest else digest

    def winner() -> None:
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyVisualPlanningOperationRepository(session)
            try:
                assert repo.reserve(_operation(seed, operation_type, key, digest)) is not None
                winner_ready.set()
                assert loser_started.wait(5)
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def loser() -> tuple[VisualPlanningOperation | None, VisualPlanningOperation | None]:
        assert winner_ready.wait(5)
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyVisualPlanningOperationRepository(session)
            try:
                loser_started.set()
                reserved = repo.reserve(_operation(seed, operation_type, key, loser_digest))
                existing = repo.get_by_key(
                    seed.context.organization_id,
                    seed.context.workspace_id,
                    seed.project_id,
                    operation_type,
                    key,
                )
                session.commit()
                return reserved, existing
            except BaseException:
                session.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner_future = pool.submit(winner)
        loser_future = pool.submit(loser)
        winner_future.result(timeout=10)
        reserved, existing = loser_future.result(timeout=10)
    assert reserved is None
    assert existing is not None and existing.request_digest == digest
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM visual_planning_operations")) == 1


@pytest.mark.parametrize(
    "operation_type",
    [
        VisualPlanningOperationType.GENERATE_STORYBOARD,
        VisualPlanningOperationType.GENERATE_SHOT_PLAN,
    ],
)
def test_winner_rollback_allows_loser_takeover(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    operation_type: VisualPlanningOperationType,
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    winner_ready, loser_started = Event(), Event()
    key = f"rollback-{operation_type.value}"

    def winner() -> None:
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyVisualPlanningOperationRepository(session)
            try:
                assert repo.reserve(_operation(seed, operation_type, key)) is not None
                winner_ready.set()
                assert loser_started.wait(5)
                session.rollback()
            except BaseException:
                session.rollback()
                raise

    def loser() -> VisualPlanningOperation | None:
        assert winner_ready.wait(5)
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyVisualPlanningOperationRepository(session)
            try:
                loser_started.set()
                reserved = repo.reserve(_operation(seed, operation_type, key))
                session.commit()
                return reserved
            except BaseException:
                session.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner_future = pool.submit(winner)
        loser_future = pool.submit(loser)
        winner_future.result(timeout=10)
        reservation = loser_future.result(timeout=10)
    assert reservation is not None
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM visual_planning_operations")) == 1


def test_storyboard_uow_atomic_rollback_removes_artifact_and_operation(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    script = _insert_script_graph(database_engine, seed, "atomic-board")
    run = _storyboard_run(script)
    version = _storyboard_version(run)
    operation = _operation(seed, VisualPlanningOperationType.GENERATE_STORYBOARD, "atomic-board")
    with (
        pytest.raises(RuntimeError, match="failpoint"),
        SqlAlchemyUnitOfWork(persistence_session_factory) as uow,
    ):
        reserved = uow.visual_planning_operations.reserve(operation)
        assert reserved is not None
        uow.storyboard_runs.add(run)
        uow.storyboard_versions.add(version)
        uow.visual_planning_operations.finalize_accepted(
            _accepted_storyboard(
                reserved, StoryboardGraph(script, run.id, version.id, version.content_digest)
            ),
            expected_version=1,
        )
        raise RuntimeError("failpoint")
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM visual_planning_operations), "
                "(SELECT count(*) FROM storyboard_runs), "
                "(SELECT count(*) FROM storyboard_versions)"
            )
        ).one()
    assert tuple(counts) == (0, 0, 0)


def test_shot_plan_uow_atomic_rollback_removes_artifact_and_operation(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    seed = _seed_project(persistence_session_factory)
    storyboard = _insert_storyboard(
        database_engine, _insert_script_graph(database_engine, seed, "atomic-shot")
    )
    run = _shot_plan_run(storyboard)
    version = _shot_plan_version(run)
    operation = _operation(seed, VisualPlanningOperationType.GENERATE_SHOT_PLAN, "atomic-shot")
    with (
        pytest.raises(RuntimeError, match="failpoint"),
        SqlAlchemyUnitOfWork(persistence_session_factory) as uow,
    ):
        reserved = uow.visual_planning_operations.reserve(operation)
        assert reserved is not None
        uow.shot_plan_runs.add(run)
        uow.shot_plan_versions.add(version)
        uow.visual_planning_operations.finalize_accepted(
            _accepted_shot(
                reserved, ShotPlanGraph(storyboard, run.id, version.id, version.content_digest)
            ),
            expected_version=1,
        )
        raise RuntimeError("failpoint")
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM visual_planning_operations), "
                "(SELECT count(*) FROM shot_plan_runs), "
                "(SELECT count(*) FROM shot_plan_versions)"
            )
        ).one()
    assert tuple(counts) == (0, 0, 0)
