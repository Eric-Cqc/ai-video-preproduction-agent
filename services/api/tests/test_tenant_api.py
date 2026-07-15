from collections.abc import Iterator
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from services.api.app.config import ApiSettings
from services.api.app.main import create_app


def headers(
    actor: str, organization_id: str | None = None, workspace_id: str | None = None
) -> dict[str, str]:
    result = {"X-Actor-Subject": actor, "X-Correlation-Id": "test-correlation"}
    if organization_id is not None:
        result["X-Organization-Id"] = organization_id
    if workspace_id is not None:
        result["X-Workspace-Id"] = workspace_id
    return result


@pytest.fixture
def persistence_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    app = create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    with TestClient(app) as client:
        yield client


def create_tenant(client: TestClient, actor: str, slug: str) -> tuple[str, str]:
    organization_response = client.post(
        "/api/v1/organizations",
        headers=headers(actor),
        json={"slug": slug, "name": slug.title()},
    )
    assert organization_response.status_code == 201, organization_response.text
    organization_id = organization_response.json()["id"]
    workspace_response = client.post(
        f"/api/v1/organizations/{organization_id}/workspaces",
        headers=headers(actor, organization_id),
        json={"slug": "main", "name": "Main"},
    )
    assert workspace_response.status_code == 201, workspace_response.text
    return organization_id, workspace_response.json()["id"]


def create_project(
    client: TestClient, actor: str, organization_id: str, workspace_id: str
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects",
        headers=headers(actor, organization_id, workspace_id),
        json={"name": "Foundation Project", "description": None},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def test_bootstrap_project_lifecycle_concurrency_and_audit(
    persistence_client: TestClient,
) -> None:
    organization_id, workspace_id = create_tenant(persistence_client, "actor:owner", "org-a")
    project = create_project(persistence_client, "actor:owner", organization_id, workspace_id)
    project_id = project["id"]
    path = (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    )
    tenant_headers = headers("actor:owner", organization_id, workspace_id)

    updated = persistence_client.patch(
        path,
        headers=tenant_headers,
        json={"expected_version": 1, "description": "Persistence proof"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = persistence_client.patch(
        path,
        headers=tenant_headers,
        json={"expected_version": 1, "name": "Stale"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"

    mass_assignment = persistence_client.patch(
        path,
        headers=tenant_headers,
        json={"expected_version": 2, "status": "archived"},
    )
    assert mass_assignment.status_code == 400

    activated = persistence_client.post(
        f"{path}/activate", headers=tenant_headers, json={"expected_version": 2}
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["version"] == 3

    archived = persistence_client.post(
        f"{path}/archive", headers=tenant_headers, json={"expected_version": 3}
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    invalid = persistence_client.post(
        f"{path}/activate", headers=tenant_headers, json={"expected_version": 4}
    )
    assert invalid.status_code == 409
    events = persistence_client.get(f"{path}/audit-events", headers=tenant_headers)
    assert events.status_code == 200
    assert [item["action"] for item in events.json()["items"]] == [
        "project.created",
        "project.updated",
        "project.activated",
        "project.archived",
    ]
    assert {item["correlation_id"] for item in events.json()["items"]} == {"test-correlation"}


def test_cross_tenant_access_is_opaque_and_project_id_is_insufficient(
    persistence_client: TestClient,
) -> None:
    org_a, workspace_a = create_tenant(persistence_client, "actor:a", "org-a")
    org_b, workspace_b = create_tenant(persistence_client, "actor:b", "org-b")
    project_b = create_project(persistence_client, "actor:b", org_b, workspace_b)

    cross_actor = persistence_client.get(
        f"/api/v1/organizations/{org_b}/workspaces/{workspace_b}/projects/{project_b['id']}",
        headers=headers("actor:a", org_b, workspace_b),
    )
    wrong_path = persistence_client.get(
        f"/api/v1/organizations/{org_a}/workspaces/{workspace_a}/projects/{project_b['id']}",
        headers=headers("actor:a", org_a, workspace_a),
    )
    mismatch = persistence_client.get(
        f"/api/v1/organizations/{org_a}/workspaces/{workspace_a}/projects/{project_b['id']}",
        headers=headers("actor:a", org_b, workspace_b),
    )
    assert cross_actor.status_code == wrong_path.status_code == mismatch.status_code == 404
    assert cross_actor.json()["error"]["message"] == "resource is not accessible"
    assert "project_b" not in cross_actor.text

    cross_mutation = persistence_client.patch(
        f"/api/v1/organizations/{org_b}/workspaces/{workspace_b}/projects/{project_b['id']}",
        headers=headers("actor:a", org_b, workspace_b),
        json={"expected_version": 1, "name": "Cross-tenant overwrite"},
    )
    assert cross_mutation.status_code == 404


def test_membership_scope_controls_workspace_access(persistence_client: TestClient) -> None:
    organization_id, workspace_id = create_tenant(persistence_client, "actor:owner", "org-a")
    membership = persistence_client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
        headers=headers("actor:owner", organization_id, workspace_id),
        json={"actor_subject": "actor:viewer", "role": "viewer"},
    )
    assert membership.status_code == 201
    project = create_project(persistence_client, "actor:owner", organization_id, workspace_id)
    view = persistence_client.get(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project['id']}",
        headers=headers("actor:viewer", organization_id, workspace_id),
    )
    mutate = persistence_client.patch(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project['id']}",
        headers=headers("actor:viewer", organization_id, workspace_id),
        json={"expected_version": 1, "name": "Forbidden"},
    )
    assert view.status_code == 200
    assert mutate.status_code == 404


def test_workspace_membership_does_not_grant_sibling_workspace_access(
    persistence_client: TestClient,
) -> None:
    organization_id, workspace_a = create_tenant(persistence_client, "actor:owner", "org-a")
    workspace_b_response = persistence_client.post(
        f"/api/v1/organizations/{organization_id}/workspaces",
        headers=headers("actor:owner", organization_id),
        json={"slug": "secondary", "name": "Secondary"},
    )
    workspace_b = workspace_b_response.json()["id"]
    membership = persistence_client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_a}/memberships",
        headers=headers("actor:owner", organization_id, workspace_a),
        json={"actor_subject": "actor:member", "role": "member"},
    )
    assert membership.status_code == 201
    project_b = create_project(persistence_client, "actor:owner", organization_id, workspace_b)
    denied = persistence_client.get(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_b}/projects/{project_b['id']}",
        headers=headers("actor:member", organization_id, workspace_b),
    )
    assert denied.status_code == 404


def test_context_validation_and_nonproduction_guard(
    persistence_client: TestClient, test_database_url: str
) -> None:
    missing = persistence_client.post(
        "/api/v1/organizations", json={"slug": "missing", "name": "Missing"}
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "invalid_request"

    production_app = create_app(
        ApiSettings(app_environment="production", database_url=test_database_url)
    )
    with TestClient(production_app) as production_client:
        blocked = production_client.post(
            "/api/v1/organizations",
            headers=headers("actor:spoofed"),
            json={"slug": "blocked", "name": "Blocked"},
        )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "temporary_identity_disabled"


def test_identifiers_are_uuid_and_errors_do_not_expose_sql(
    persistence_client: TestClient,
) -> None:
    organization_id, _ = create_tenant(persistence_client, "actor:owner", "org-a")
    UUID(organization_id)
    duplicate = persistence_client.post(
        "/api/v1/organizations",
        headers=headers("actor:other"),
        json={"slug": "org-a", "name": "Duplicate"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "organization_slug_conflict"
    assert "sql" not in duplicate.text.lower()
    assert "constraint" not in duplicate.text.lower()
