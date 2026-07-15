from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api.app.config import ApiSettings
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, fixture, headers


@pytest.fixture
def ingestion_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    with TestClient(
        create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    ) as client:
        yield client


def _path(organization_id: str, workspace_id: str, project_id: str) -> str:
    return (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}"
        f"/projects/{project_id}/brief-ingestions"
    )


def _payload(title: str = "Imported Brief") -> dict[str, Any]:
    return {
        "operation": "create_brief",
        "title": title,
        "structured_content": fixture("valid-structured-brief-v1.json"),
        "source_type": "api_structured",
        "source_reference": "external-record:42",
        "change_summary": "Controlled structured ingestion",
    }


def test_create_replay_conflict_and_scoped_get(ingestion_client: TestClient) -> None:
    organization_id, workspace_id, project_id = bootstrap(ingestion_client, "ingestion-org")
    request_headers = headers("actor:owner", organization_id, workspace_id)
    request_headers["Idempotency-Key"] = "ingestion-key-0001"
    path = _path(organization_id, workspace_id, project_id)

    created = ingestion_client.post(path, headers=request_headers, json=_payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["replayed"] is False
    assert "payload_digest" not in body
    assert body["correlation_id"] == "brief-test"

    replay = ingestion_client.post(path, headers=request_headers, json=_payload())
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["ingestion_id"] == body["ingestion_id"]
    assert replay.json()["result"]["brief"]["id"] == body["result"]["brief"]["id"]
    assert (
        replay.json()["result"]["current_version"]["id"] == body["result"]["current_version"]["id"]
    )
    brief_id = body["result"]["brief"]["id"]
    events = ingestion_client.get(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/"
        f"{project_id}/briefs/{brief_id}/audit-events",
        headers=request_headers,
    ).json()["items"]
    assert [event["action"] for event in events] == ["brief.ingestion_accepted"]

    conflict = ingestion_client.post(path, headers=request_headers, json=_payload("Changed"))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert "constraint" not in conflict.text.lower()

    fetched = ingestion_client.get(f"{path}/{body['ingestion_id']}", headers=request_headers)
    assert fetched.status_code == 200
    assert fetched.json()["ingestion_id"] == body["ingestion_id"]

    other_organization, other_workspace, other_project = bootstrap(
        ingestion_client, "other-ingestion-org"
    )
    hidden = ingestion_client.get(
        f"{_path(other_organization, other_workspace, other_project)}/{body['ingestion_id']}",
        headers=headers("actor:owner", other_organization, other_workspace),
    )
    assert hidden.status_code == 404


@pytest.mark.parametrize("key", [None, "short", "has space key", " padded-key-0001"])
def test_idempotency_key_is_required_and_bounded(
    ingestion_client: TestClient, key: str | None
) -> None:
    organization_id, workspace_id, project_id = bootstrap(
        ingestion_client, f"key-org-{abs(hash(key)) % 100000}"
    )
    request_headers = headers("actor:owner", organization_id, workspace_id)
    if key is not None:
        request_headers["Idempotency-Key"] = key
    response = ingestion_client.post(
        _path(organization_id, workspace_id, project_id),
        headers=request_headers,
        json=_payload(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_invalid_provenance_extra_fields_and_oversized_body(ingestion_client: TestClient) -> None:
    organization_id, workspace_id, project_id = bootstrap(ingestion_client, "bounds-org")
    request_headers = headers("actor:owner", organization_id, workspace_id)
    request_headers["Idempotency-Key"] = "ingestion-key-bounds"
    path = _path(organization_id, workspace_id, project_id)

    invalid = _payload()
    invalid["source_reference"] = "/tmp/customer.pdf"
    assert ingestion_client.post(path, headers=request_headers, json=invalid).status_code == 400

    extra = _payload()
    extra["status"] = "accepted"
    assert ingestion_client.post(path, headers=request_headers, json=extra).status_code == 400

    oversized = _payload()
    oversized["title"] = "x" * 300_000
    response = ingestion_client.post(path, headers=request_headers, json=oversized)
    assert response.status_code == 413


def test_version_ingestion_preserves_approved_predecessor_and_replays_after_advance(
    ingestion_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(ingestion_client, "version-ingestion")
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    create_headers = {**tenant_headers, "Idempotency-Key": "create-version-base"}
    project_ingestions = _path(organization_id, workspace_id, project_id)
    created = ingestion_client.post(
        project_ingestions, headers=create_headers, json=_payload()
    ).json()
    brief = created["result"]["brief"]
    original = created["result"]["current_version"]
    brief_path = (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
        f"/briefs/{brief['id']}"
    )
    assert (
        ingestion_client.post(
            f"{brief_path}/submit",
            headers=tenant_headers,
            json={"expected_brief_version": 1, "expected_current_version_id": original["id"]},
        ).status_code
        == 200
    )
    approved = ingestion_client.post(
        f"{brief_path}/approve",
        headers=tenant_headers,
        json={"expected_brief_version": 2, "expected_current_version_id": original["id"]},
    )
    assert approved.status_code == 200
    immutable_before = ingestion_client.get(
        f"{brief_path}/versions/{original['id']}", headers=tenant_headers
    ).json()

    version_headers = {**tenant_headers, "Idempotency-Key": "version-ingestion-0001"}
    version_payload = {
        "operation": "create_version",
        "expected_brief_version": 3,
        "expected_current_version_id": original["id"],
        "source_version_id": original["id"],
        "structured_content": fixture("valid-structured-brief-v1.json"),
        "source_type": "imported_structured",
        "source_reference": "external-record:43",
        "change_summary": "Successor of approved snapshot",
    }
    accepted = ingestion_client.post(
        f"{brief_path}/ingestions", headers=version_headers, json=version_payload
    )
    assert accepted.status_code == 201, accepted.text
    successor = accepted.json()["result"]["current_version"]
    assert successor["supersedes_version_id"] == original["id"]
    assert (
        ingestion_client.get(
            f"{brief_path}/versions/{original['id']}", headers=tenant_headers
        ).json()
        == immutable_before
    )

    next_headers = {**tenant_headers, "Idempotency-Key": "version-ingestion-0002"}
    next_payload = {
        **version_payload,
        "expected_brief_version": 4,
        "expected_current_version_id": successor["id"],
        "source_version_id": successor["id"],
        "change_summary": "Advance aggregate again",
    }
    assert (
        ingestion_client.post(
            f"{brief_path}/ingestions", headers=next_headers, json=next_payload
        ).status_code
        == 201
    )

    replay = ingestion_client.post(
        f"{brief_path}/ingestions", headers=version_headers, json=version_payload
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["result"]["current_version"]["id"] == successor["id"]
