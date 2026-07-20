import json
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.app.application.brief_services import BriefApplicationService, BriefBundle
from services.api.app.application.context import TenantContext
from services.api.app.application.model_provider import (
    DeterministicFakeProvider,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.config import ApiSettings
from services.api.app.domain import BriefSourceType
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, headers
from services.api.tests.test_brief_extraction_foundation import FIXTURES, _source

CREATIVE = Path(__file__).resolve().parents[3] / "packages" / "test-fixtures" / "creative"


@pytest.fixture
def creative_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    app = create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    with TestClient(app) as client:
        yield client


def _concept_provider() -> DeterministicFakeProvider:
    concepts = [json.loads((CREATIVE / "valid-concept-v1.json").read_text()) for _ in range(3)]
    for index, concept in enumerate(concepts, 1):
        concept["title"] = f"Concept {index}"
    return DeterministicFakeProvider(
        ProviderOutcome(ProviderOutcomeStatus.SUCCESS, json.dumps({"concepts": concepts}))
    )


def _brief(
    session_factory: SessionFactory, tmp_path: Path
) -> tuple[TenantContext, UUID, BriefBundle]:
    context, project_id, *_ = _source(session_factory, tmp_path)
    content = json.loads((FIXTURES / "valid-structured-brief-v1.json").read_text())
    created = BriefApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory)).create_brief(
        context,
        project_id,
        title="Creative API source",
        structured_content=content,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Creative API input",
    )
    return context, project_id, created


def _brief_path(context: TenantContext, project_id: UUID, brief: BriefBundle) -> str:
    return (
        f"/api/v1/organizations/{context.organization_id}/workspaces/{context.workspace_id}"
        f"/projects/{project_id}/briefs/{brief.brief.id}/versions/{brief.current_version.id}"
    )


def _app(client: TestClient) -> FastAPI:
    return client.app  # type: ignore[return-value]


def test_creative_api_generation_selection_script_replay_and_permissions(
    creative_client: TestClient, persistence_session_factory: SessionFactory, tmp_path: Path
) -> None:
    context, project_id, brief = _brief(persistence_session_factory, tmp_path)
    _app(creative_client).state.creative_application_service.provider = _concept_provider()
    owner = headers(context.actor_subject, str(context.organization_id), str(context.workspace_id))
    generated = creative_client.post(
        f"{_brief_path(context, project_id, brief)}/concept-runs",
        headers={**owner, "Idempotency-Key": "concept-api-1"},
        json={},
    )
    assert generated.status_code == 201, generated.text
    body = generated.json()
    assert len(body["candidates"]) == 3
    run_id, candidate_id = body["run"]["id"], body["candidates"][0]["id"]
    replay = creative_client.post(
        f"{_brief_path(context, project_id, brief)}/concept-runs",
        headers={**owner, "Idempotency-Key": "concept-api-1"},
        json={},
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True

    member = "actor:creative-viewer"
    membership = creative_client.post(
        f"/api/v1/organizations/{context.organization_id}/workspaces/{context.workspace_id}/memberships",
        headers=owner,
        json={"actor_subject": member, "role": "viewer"},
    )
    assert membership.status_code == 201
    viewer = headers(member, str(context.organization_id), str(context.workspace_id))
    candidate_path = (
        f"/api/v1/organizations/{context.organization_id}/workspaces/{context.workspace_id}"
        f"/projects/{project_id}/concept-runs/{run_id}/candidates"
    )
    assert creative_client.get(candidate_path, headers=viewer).status_code == 200
    denied = creative_client.post(
        f"{candidate_path}/{candidate_id}/select",
        headers={**viewer, "Idempotency-Key": "viewer-select"},
        json={},
    )
    assert denied.status_code == 403

    selected = creative_client.post(
        f"{candidate_path}/{candidate_id}/select",
        headers={**owner, "Idempotency-Key": "select-api-1"},
        json={},
    )
    assert selected.status_code == 201, selected.text
    _app(creative_client).state.creative_application_service.provider = DeterministicFakeProvider(
        ProviderOutcome(
            ProviderOutcomeStatus.SUCCESS, (CREATIVE / "valid-script-v1.json").read_text()
        )
    )
    script_path = candidate_path.rsplit("/candidates", 1)[0] + "/scripts"
    script = creative_client.post(
        script_path, headers={**owner, "Idempotency-Key": "script-api-1"}, json={}
    )
    assert script.status_code == 201, script.text
    assert (
        creative_client.get(
            script_path.rsplit("/concept-runs", 1)[0]
            + f"/scripts/{script.json()['script_version_id']}",
            headers=owner,
        ).status_code
        == 200
    )


def test_creative_routes_use_one_opaque_not_found_shape(
    creative_client: TestClient, persistence_session_factory: SessionFactory, tmp_path: Path
) -> None:
    context, project_id, brief = _brief(persistence_session_factory, tmp_path)
    _app(creative_client).state.creative_application_service.provider = _concept_provider()
    owner = headers(context.actor_subject, str(context.organization_id), str(context.workspace_id))
    generated = creative_client.post(
        f"{_brief_path(context, project_id, brief)}/concept-runs",
        headers={**owner, "Idempotency-Key": "opaque-concept"},
        json={},
    ).json()
    run_id = generated["run"]["id"]
    other_org, other_workspace, other_project = bootstrap(creative_client, "creative-opaque")
    cases = [
        (
            f"/api/v1/organizations/{context.organization_id}/workspaces/{context.workspace_id}"
            f"/projects/{project_id}/concept-runs/{uuid4()}",
            owner,
        ),
        (
            f"/api/v1/organizations/{other_org}/workspaces/{other_workspace}"
            f"/projects/{other_project}/concept-runs/{run_id}",
            headers("actor:owner", other_org, other_workspace),
        ),
    ]
    bodies = []
    for path, request_headers in cases:
        response = creative_client.get(path, headers=request_headers)
        assert response.status_code == 404
        bodies.append(response.json())
    assert bodies[0] == bodies[1]
    assert str(run_id) not in str(bodies[0])
