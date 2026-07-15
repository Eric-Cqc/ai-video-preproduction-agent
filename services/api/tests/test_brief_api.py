import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from services.api.app.config import ApiSettings
from services.api.app.main import create_app

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "test-fixtures" / "brief"


@pytest.fixture
def brief_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    app = create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    with TestClient(app) as client:
        yield client


def headers(
    actor: str, organization_id: str | None = None, workspace_id: str | None = None
) -> dict[str, str]:
    result = {"X-Actor-Subject": actor, "X-Correlation-Id": "brief-test"}
    if organization_id:
        result["X-Organization-Id"] = organization_id
    if workspace_id:
        result["X-Workspace-Id"] = workspace_id
    return result


def fixture(name: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / name).read_text()))


def bootstrap(client: TestClient, slug: str = "brief-org") -> tuple[str, str, str]:
    actor = "actor:owner"
    organization = client.post(
        "/api/v1/organizations",
        headers=headers(actor),
        json={"slug": slug, "name": "Brief Org"},
    ).json()
    organization_id = organization["id"]
    workspace = client.post(
        f"/api/v1/organizations/{organization_id}/workspaces",
        headers=headers(actor, organization_id),
        json={"slug": "main", "name": "Main"},
    ).json()
    workspace_id = workspace["id"]
    project = client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects",
        headers=headers(actor, organization_id, workspace_id),
        json={"name": "Video Project", "description": None},
    ).json()
    return organization_id, workspace_id, project["id"]


def base_path(organization_id: str, workspace_id: str, project_id: str) -> str:
    return (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}"
        f"/projects/{project_id}/briefs"
    )


def create_brief(
    client: TestClient,
    organization_id: str,
    workspace_id: str,
    project_id: str,
    *,
    content: dict[str, object] | None = None,
) -> dict[str, Any]:
    response = client.post(
        base_path(organization_id, workspace_id, project_id),
        headers=headers("actor:owner", organization_id, workspace_id),
        json={
            "title": "Launch Brief",
            "structured_content": content or fixture("valid-structured-brief-v1.json"),
            "source_type": "manual",
            "change_summary": "Initial structured Brief",
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_create_read_version_and_stale_pointer_are_atomic(brief_client: TestClient) -> None:
    organization_id, workspace_id, project_id = bootstrap(brief_client)
    created = create_brief(brief_client, organization_id, workspace_id, project_id)
    brief = created["brief"]
    current = created["current_version"]
    path = f"{base_path(organization_id, workspace_id, project_id)}/{brief['id']}"
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    assert current["content_schema_version"] == "1.0.0"
    assert created["issues"] == []

    version_response = brief_client.post(
        f"{path}/versions",
        headers=tenant_headers,
        json={
            "expected_brief_version": 1,
            "expected_current_version_id": current["id"],
            "source_version_id": current["id"],
            "structured_content": fixture("valid-structured-brief-v1.json"),
            "source_type": "manual",
            "change_summary": "Second immutable snapshot",
        },
    )
    assert version_response.status_code == 201, version_response.text
    versioned = version_response.json()
    assert versioned["brief"]["latest_version_number"] == 2
    assert versioned["brief"]["version"] == 2
    assert versioned["current_version"]["supersedes_version_id"] == current["id"]

    stale = brief_client.post(
        f"{path}/versions",
        headers=tenant_headers,
        json={
            "expected_brief_version": 1,
            "expected_current_version_id": current["id"],
            "source_version_id": current["id"],
            "structured_content": fixture("valid-structured-brief-v1.json"),
            "source_type": "manual",
            "change_summary": "Stale snapshot",
        },
    )
    assert stale.status_code == 409
    versions = brief_client.get(f"{path}/versions", headers=tenant_headers).json()["items"]
    assert [item["version_number"] for item in versions] == [1, 2]
    assert versions[0]["lifecycle_state"] == "superseded"
    events = brief_client.get(f"{path}/audit-events", headers=tenant_headers).json()["items"]
    assert [event["action"] for event in events] == ["brief.created", "brief.version_created"]


def test_approved_version_remains_entirely_immutable_when_superseded(
    brief_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(brief_client)
    created = create_brief(brief_client, organization_id, workspace_id, project_id)
    brief = created["brief"]
    version = created["current_version"]
    path = f"{base_path(organization_id, workspace_id, project_id)}/{brief['id']}"
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    submitted = brief_client.post(
        f"{path}/submit",
        headers=tenant_headers,
        json={"expected_brief_version": 1, "expected_current_version_id": version["id"]},
    )
    assert submitted.status_code == 200
    approved = brief_client.post(
        f"{path}/approve",
        headers=tenant_headers,
        json={"expected_brief_version": 2, "expected_current_version_id": version["id"]},
    )
    assert approved.status_code == 200
    old_version = approved.json()["current_version"]

    new_version = brief_client.post(
        f"{path}/versions",
        headers=tenant_headers,
        json={
            "expected_brief_version": 3,
            "expected_current_version_id": old_version["id"],
            "source_version_id": old_version["id"],
            "structured_content": fixture("valid-structured-brief-v1.json"),
            "source_type": "manual",
            "change_summary": "Approved snapshot successor",
        },
    )
    assert new_version.status_code == 201, new_version.text
    created_successor = new_version.json()
    persisted_old = brief_client.get(f"{path}/versions/{old_version['id']}", headers=tenant_headers)
    assert persisted_old.status_code == 200
    assert persisted_old.json() == old_version
    assert persisted_old.json()["lifecycle_state"] == "approved"
    assert persisted_old.json()["approved_at"] is not None
    assert persisted_old.json()["approved_by_actor_subject"] == "actor:owner"
    assert persisted_old.json()["structured_content"] == old_version["structured_content"]
    assert created_successor["current_version"]["supersedes_version_id"] == old_version["id"]
    assert (
        created_successor["brief"]["current_version_id"]
        == created_successor["current_version"]["id"]
    )
    assert created_successor["brief"]["status"] == "draft"
    assert created_successor["brief"]["latest_version_number"] == 2
    assert created_successor["brief"]["version"] == 4
    events = brief_client.get(f"{path}/audit-events", headers=tenant_headers).json()["items"]
    assert [event["action"] for event in events] == [
        "brief.created",
        "brief.submitted_for_review",
        "brief.approved",
        "brief.version_created",
    ]


def test_review_approval_blockers_issue_resolution_and_roles(brief_client: TestClient) -> None:
    organization_id, workspace_id, project_id = bootstrap(brief_client)
    created = create_brief(
        brief_client,
        organization_id,
        workspace_id,
        project_id,
        content=fixture("incomplete-structured-brief-v1.json"),
    )
    brief = created["brief"]
    version = created["current_version"]
    assert created["issues"]
    path = f"{base_path(organization_id, workspace_id, project_id)}/{brief['id']}"
    owner_headers = headers("actor:owner", organization_id, workspace_id)
    submitted = brief_client.post(
        f"{path}/submit",
        headers=owner_headers,
        json={"expected_brief_version": 1, "expected_current_version_id": version["id"]},
    )
    assert submitted.status_code == 200
    blocked = brief_client.post(
        f"{path}/approve",
        headers=owner_headers,
        json={"expected_brief_version": 2, "expected_current_version_id": version["id"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "brief_approval_blocked"

    aggregate_version = 2
    for issue in created["issues"]:
        closed = brief_client.post(
            f"{path}/versions/{version['id']}/issues/{issue['id']}/resolve",
            headers=owner_headers,
            json={
                "expected_brief_version": aggregate_version,
                "expected_current_version_id": version["id"],
                "expected_issue_version": 1,
                "resolution_note": "Requirement confirmed outside this foundation test",
            },
        )
        assert closed.status_code == 200, closed.text
        aggregate_version += 1
    approved = brief_client.post(
        f"{path}/approve",
        headers=owner_headers,
        json={
            "expected_brief_version": aggregate_version,
            "expected_current_version_id": version["id"],
        },
    )
    assert approved.status_code == 200
    assert approved.json()["brief"]["status"] == "approved"


def test_tenant_isolation_mass_assignment_and_contract_validation(brief_client: TestClient) -> None:
    org_a, workspace_a, project_a = bootstrap(brief_client, "org-a")
    created = create_brief(brief_client, org_a, workspace_a, project_a)
    brief_id = created["brief"]["id"]
    org_b, workspace_b, project_b = bootstrap(brief_client, "org-b")

    cross = brief_client.get(
        f"{base_path(org_b, workspace_b, project_b)}/{brief_id}",
        headers=headers("actor:owner", org_b, workspace_b),
    )
    assert cross.status_code == 404

    invalid = brief_client.post(
        base_path(org_a, workspace_a, project_a),
        headers=headers("actor:owner", org_a, workspace_a),
        json={
            "title": "Invalid",
            "structured_content": fixture("invalid-unknown-field.json"),
            "source_type": "manual",
            "change_summary": "Must fail",
            "status": "approved",
        },
    )
    assert invalid.status_code == 400
    assert brief_client.get(
        base_path(org_a, workspace_a, project_a),
        headers=headers("actor:owner", org_a, workspace_a),
    ).json()["items"] == [created["brief"]]


def test_member_issue_workflow_admin_approval_and_viewer_read_only(
    brief_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(brief_client)
    owner_headers = headers("actor:owner", organization_id, workspace_id)
    membership_path = (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships"
    )
    for actor, role in (("actor:member", "member"), ("actor:viewer", "viewer")):
        response = brief_client.post(
            membership_path,
            headers=owner_headers,
            json={"actor_subject": actor, "role": role},
        )
        assert response.status_code == 201

    created = create_brief(brief_client, organization_id, workspace_id, project_id)
    brief = created["brief"]
    version = created["current_version"]
    path = f"{base_path(organization_id, workspace_id, project_id)}/{brief['id']}"
    member_headers = headers("actor:member", organization_id, workspace_id)
    issue_response = brief_client.post(
        f"{path}/versions/{version['id']}/issues",
        headers=member_headers,
        json={
            "expected_brief_version": 1,
            "expected_current_version_id": version["id"],
            "issue_type": "ambiguous",
            "field_path": "brand.tone",
            "severity": "blocking",
            "message": "Confirm the primary tone",
        },
    )
    assert issue_response.status_code == 201
    issue = issue_response.json()
    dismissed = brief_client.post(
        f"{path}/versions/{version['id']}/issues/{issue['id']}/dismiss",
        headers=member_headers,
        json={
            "expected_brief_version": 2,
            "expected_current_version_id": version["id"],
            "expected_issue_version": 1,
            "resolution_note": "Not required for this bounded Brief",
        },
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    submitted = brief_client.post(
        f"{path}/submit",
        headers=member_headers,
        json={"expected_brief_version": 3, "expected_current_version_id": version["id"]},
    )
    assert submitted.status_code == 200
    denied_approval = brief_client.post(
        f"{path}/approve",
        headers=member_headers,
        json={"expected_brief_version": 4, "expected_current_version_id": version["id"]},
    )
    assert denied_approval.status_code == 404
    approved = brief_client.post(
        f"{path}/approve",
        headers=owner_headers,
        json={"expected_brief_version": 4, "expected_current_version_id": version["id"]},
    )
    assert approved.status_code == 200

    immutable_approval = brief_client.post(
        f"{path}/versions/{version['id']}/issues",
        headers=owner_headers,
        json={
            "expected_brief_version": 5,
            "expected_current_version_id": version["id"],
            "issue_type": "missing",
            "field_path": "objective.primary_goal",
            "severity": "blocking",
            "message": "Must require a new draft version",
        },
    )
    assert immutable_approval.status_code == 409

    viewer_headers = headers("actor:viewer", organization_id, workspace_id)
    assert brief_client.get(path, headers=viewer_headers).status_code == 200
    denied_mutation = brief_client.post(
        f"{path}/versions/{version['id']}/issues",
        headers=viewer_headers,
        json={
            "expected_brief_version": 5,
            "expected_current_version_id": version["id"],
            "issue_type": "missing",
            "field_path": "objective.primary_goal",
            "severity": "warning",
            "message": "Denied",
        },
    )
    assert denied_mutation.status_code == 404


def test_request_size_guard_rejects_before_route_processing(brief_client: TestClient) -> None:
    response = brief_client.post(
        "/api/v1/organizations",
        headers={**headers("actor:owner"), "Content-Length": "262145"},
        content=b"{}",
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
