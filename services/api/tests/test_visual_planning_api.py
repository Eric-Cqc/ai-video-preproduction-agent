from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from services.api.app.application.model_provider import DeterministicVisualPlanningProvider
from services.api.app.config import ApiSettings
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.main import create_app
from services.api.tests.test_brief_api import headers
from services.api.tests.test_visual_planning_persistence import (
    _insert_script_graph,
    _seed_project,
)
from services.api.tests.test_visual_planning_services import _make_script_usable


@pytest.fixture
def creative_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    app = create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    with TestClient(app) as client:
        yield client


def _app(client: TestClient) -> FastAPI:
    return client.app  # type: ignore[return-value]


def test_visual_planning_api_success_replay_permissions_and_opaque_404(
    creative_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
) -> None:
    seed = _seed_project(persistence_session_factory, name="Stage 12B API")
    graph = _insert_script_graph(database_engine, seed, "api")
    _make_script_usable(database_engine, graph.script_version_id)
    _app(
        creative_client
    ).state.visual_planning_application_service.provider = DeterministicVisualPlanningProvider()
    owner_headers = headers(
        seed.context.actor_subject,
        str(seed.context.organization_id),
        str(seed.context.workspace_id),
    )
    path = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/{seed.context.workspace_id}"
        f"/projects/{seed.project_id}/scripts/{graph.script_version_id}/storyboards"
    )
    first = creative_client.post(
        path, headers={**owner_headers, "Idempotency-Key": "api-board-1"}, json={}
    )
    assert first.status_code == 201, first.text
    assert "content_digest" not in first.text
    replay = creative_client.post(
        path, headers={**owner_headers, "Idempotency-Key": "api-board-1"}, json={}
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    board_version_id = first.json()["version"]["id"]
    get_path = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/{seed.context.workspace_id}"
        f"/projects/{seed.project_id}/storyboards/{board_version_id}"
    )
    assert creative_client.get(get_path, headers=owner_headers).status_code == 200
    shot_path = f"{get_path}/shot-plans"
    shot = creative_client.post(
        shot_path, headers={**owner_headers, "Idempotency-Key": "api-shot-1"}, json={}
    )
    assert shot.status_code == 201, shot.text
    assert "content_digest" not in shot.text
    assert creative_client.post(path, headers=owner_headers, json={}).status_code == 400
    assert (
        creative_client.post(
            path,
            headers={**owner_headers, "Idempotency-Key": "api-extra-1"},
            json={"status": "accepted"},
        ).status_code
        == 400
    )

    viewer = "actor:visual-viewer"
    membership_path = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/{seed.context.workspace_id}"
        "/memberships"
    )
    assert (
        creative_client.post(
            membership_path,
            headers=owner_headers,
            json={"actor_subject": viewer, "role": "viewer"},
        ).status_code
        == 201
    )
    viewer_headers = headers(
        viewer, str(seed.context.organization_id), str(seed.context.workspace_id)
    )
    assert creative_client.get(get_path, headers=viewer_headers).status_code == 200
    assert (
        creative_client.post(
            path, headers={**viewer_headers, "Idempotency-Key": "viewer-board-1"}, json={}
        ).status_code
        == 403
    )
