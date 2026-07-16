from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from services.api.app.config import ApiSettings
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, headers
from services.api.tests.test_candidate_review import _candidate


@pytest.fixture
def brief_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    app = create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    with TestClient(app) as client:
        yield client


def _path(organization_id: object, workspace_id: object, project_id: object, run_id: object) -> str:
    return (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}"
        f"/projects/{project_id}/brief-extraction-runs/{run_id}"
    )


@pytest.mark.parametrize("role", ["owner", "admin", "member", "viewer"])
@pytest.mark.parametrize("action", ["accept", "reject"])
def test_candidate_api_roles_and_viewer_is_read_only(
    brief_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    tmp_path: Path,
    role: Literal["owner", "admin", "member", "viewer"],
    action: Literal["accept", "reject"],
) -> None:
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    actor = context.actor_subject if role == "owner" else f"actor:{role}"
    tenant_headers = headers(actor, str(context.organization_id), str(context.workspace_id))
    if role != "owner":
        membership = brief_client.post(
            (
                f"/api/v1/organizations/{context.organization_id}/workspaces/"
                f"{context.workspace_id}/memberships"
            ),
            headers=headers(
                context.actor_subject,
                str(context.organization_id),
                str(context.workspace_id),
            ),
            json={"actor_subject": actor, "role": role},
        )
        assert membership.status_code == 201, membership.text
    path = _path(context.organization_id, context.workspace_id, project_id, run.id)

    assert brief_client.get(path, headers=tenant_headers).status_code == 200
    candidate = brief_client.get(f"{path}/candidate", headers=tenant_headers)
    assert candidate.status_code == 200
    assert set(candidate.json()) == {"run_id", "candidate", "candidate_issues"}

    payload = (
        {"title": "API reviewed Brief"}
        if action == "accept"
        else {"reason": "inaccurate", "note": "Human review"}
    )
    response = brief_client.post(
        f"{path}/{action}",
        headers={**tenant_headers, "Idempotency-Key": f"{role}-{action}"},
        json=payload,
    )
    assert response.status_code == (403 if role == "viewer" else 201), response.text
    with database_engine.connect() as connection:
        mutations = connection.scalar(text("SELECT count(*) FROM brief_candidate_reviews"))
    assert mutations == (0 if role == "viewer" else 1)


def test_candidate_api_uses_one_opaque_not_found_shape(
    brief_client: TestClient,
    persistence_session_factory: SessionFactory,
    tmp_path: Path,
) -> None:
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    other_org, other_workspace, other_project = bootstrap(brief_client, "opaque-other")
    valid_headers = headers(
        context.actor_subject, str(context.organization_id), str(context.workspace_id)
    )
    cases = [
        (
            _path(other_org, other_workspace, other_project, run.id),
            headers("actor:owner", other_org, other_workspace),
        ),
        (
            _path(context.organization_id, uuid4(), project_id, run.id),
            valid_headers,
        ),
        (
            _path(context.organization_id, context.workspace_id, uuid4(), run.id),
            valid_headers,
        ),
        (
            _path(context.organization_id, context.workspace_id, project_id, uuid4()),
            valid_headers,
        ),
        (
            _path(other_org, context.workspace_id, project_id, run.id),
            headers("actor:owner", other_org, other_workspace),
        ),
    ]
    bodies = []
    for path, request_headers in cases:
        response = brief_client.get(f"{path}/candidate", headers=request_headers)
        assert response.status_code == 404
        bodies.append(response.json())

    assert all(body == bodies[0] for body in bodies)
    serialized = str(bodies[0])
    assert str(run.id) not in serialized
    assert str(project_id) not in serialized
