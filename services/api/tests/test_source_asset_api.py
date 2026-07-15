from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from services.api.app.config import ApiSettings
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, headers


@pytest.fixture
def source_asset_client(test_database_url: str, clean_database: None) -> Iterator[TestClient]:
    del clean_database
    with TestClient(
        create_app(ApiSettings(app_environment="test", database_url=test_database_url))
    ) as client:
        yield client


def _path(organization_id: str, workspace_id: str, project_id: str) -> str:
    return (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}"
        f"/projects/{project_id}/source-assets"
    )


def _payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "display_name": "Creative Source",
        "original_filename": "creative-source.pdf",
        "media_type": "application/pdf",
        "byte_size": 1024,
        "checksum_algorithm": "sha256",
        "checksum_value": "a" * 64,
        "source_type": "api_declared",
        "source_reference": "https://example.invalid/source",
        "external_record_id": "external-1",
        "declared_created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _version_metadata(**overrides: object) -> dict[str, Any]:
    payload = _payload(**overrides)
    payload.pop("display_name")
    return payload


def _create(
    client: TestClient,
    organization_id: str,
    workspace_id: str,
    project_id: str,
    *,
    key: str = "source-key-0001",
    actor: str = "actor:owner",
    **overrides: object,
) -> dict[str, Any]:
    request_headers = headers(actor, organization_id, workspace_id)
    request_headers["Idempotency-Key"] = key
    response = client.post(
        _path(organization_id, workspace_id, project_id),
        headers=request_headers,
        json=_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_source_asset_create_replay_conflict_get_and_list(
    source_asset_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(source_asset_client, "source-api")
    request_headers = headers("actor:owner", organization_id, workspace_id)
    request_headers["Idempotency-Key"] = "source-key-0001"
    path = _path(organization_id, workspace_id, project_id)

    created = source_asset_client.post(path, headers=request_headers, json=_payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["replayed"] is False
    assert body["duplicate_content_detected"] is False
    assert "request_digest" not in created.text
    assert "idempotency" not in created.text.lower()
    asset_id = body["source_asset"]["id"]
    version_id = body["current_version"]["id"]

    replay = source_asset_client.post(path, headers=request_headers, json=_payload())
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["source_asset"]["id"] == asset_id

    conflict = source_asset_client.post(
        path, headers=request_headers, json=_payload(byte_size=2048)
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert "source-key-0001" not in conflict.text

    fetched = source_asset_client.get(
        f"{path}/{asset_id}", headers=headers("actor:owner", organization_id, workspace_id)
    )
    assert fetched.status_code == 200
    assert fetched.json()["source_asset"]["id"] == asset_id
    assert fetched.json()["current_version"]["id"] == version_id

    listed = source_asset_client.get(
        f"{path}?limit=1&offset=0", headers=headers("actor:owner", organization_id, workspace_id)
    )
    assert listed.status_code == 200
    assert listed.json()["limit"] == 1
    assert [item["id"] for item in listed.json()["items"]] == [asset_id]


def test_source_asset_create_version_archive_and_replay_after_advance(
    source_asset_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(source_asset_client, "source-version-api")
    created = _create(source_asset_client, organization_id, workspace_id, project_id)
    asset = created["source_asset"]
    version = created["current_version"]
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    version_headers = {**tenant_headers, "Idempotency-Key": "source-version-key"}
    path = _path(organization_id, workspace_id, project_id)

    version_payload = {
        "expected_source_asset_version": asset["version"],
        "expected_current_version_id": asset["current_version_id"],
        "source_version_id": version["id"],
        **_version_metadata(
            original_filename="creative-source-v2.pdf",
            byte_size=2048,
            checksum_value="b" * 64,
        ),
    }
    versioned = source_asset_client.post(
        f"{path}/{asset['id']}/versions", headers=version_headers, json=version_payload
    )
    assert versioned.status_code == 201, versioned.text
    successor = versioned.json()["current_version"]
    assert successor["supersedes_version_id"] == version["id"]

    stale = source_asset_client.post(
        f"{path}/{asset['id']}/versions",
        headers={**tenant_headers, "Idempotency-Key": "stale-source-version"},
        json=version_payload,
    )
    assert stale.status_code == 409

    replay = source_asset_client.post(
        f"{path}/{asset['id']}/versions", headers=version_headers, json=version_payload
    )
    assert replay.status_code == 200
    assert replay.json()["current_version"]["id"] == successor["id"]

    versions = source_asset_client.get(f"{path}/{asset['id']}/versions", headers=tenant_headers)
    assert [item["version_number"] for item in versions.json()["items"]] == [1, 2]
    assert (
        source_asset_client.get(
            f"{path}/{asset['id']}/versions/{successor['id']}", headers=tenant_headers
        ).json()["id"]
        == successor["id"]
    )

    archive = source_asset_client.post(
        f"{path}/{asset['id']}/archive",
        headers={**tenant_headers, "Idempotency-Key": "archive-source-key"},
        json={
            "expected_source_asset_version": 2,
            "expected_current_version_id": successor["id"],
        },
    )
    assert archive.status_code == 200
    assert archive.json()["source_asset"]["status"] == "archived"

    archived_version = source_asset_client.post(
        f"{path}/{asset['id']}/versions",
        headers={**tenant_headers, "Idempotency-Key": "archived-source-version"},
        json={
            **version_payload,
            "expected_source_asset_version": 3,
            "expected_current_version_id": successor["id"],
            "source_version_id": successor["id"],
        },
    )
    assert archived_version.status_code == 409


def test_source_asset_roles_opaque_cross_tenant_and_invalid_payloads(
    source_asset_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(source_asset_client, "source-roles")
    base = _create(source_asset_client, organization_id, workspace_id, project_id)
    asset_id = base["source_asset"]["id"]
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    source_asset_client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
        headers=tenant_headers,
        json={"actor_subject": "actor:viewer", "role": "viewer"},
    )
    source_asset_client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
        headers=tenant_headers,
        json={"actor_subject": "actor:member", "role": "member"},
    )

    assert (
        source_asset_client.get(
            f"{_path(organization_id, workspace_id, project_id)}/{asset_id}",
            headers=headers("actor:viewer", organization_id, workspace_id),
        ).status_code
        == 200
    )
    viewer_headers = headers("actor:viewer", organization_id, workspace_id)
    viewer_headers["Idempotency-Key"] = "viewer-create-key"
    assert (
        source_asset_client.post(
            _path(organization_id, workspace_id, project_id),
            headers=viewer_headers,
            json=_payload(checksum_value="c" * 64),
        ).status_code
        == 404
    )
    member_headers = headers("actor:member", organization_id, workspace_id)
    member_headers["Idempotency-Key"] = "member-archive-key"
    assert (
        source_asset_client.post(
            f"{_path(organization_id, workspace_id, project_id)}/{asset_id}/archive",
            headers=member_headers,
            json={
                "expected_source_asset_version": 1,
                "expected_current_version_id": base["source_asset"]["current_version_id"],
            },
        ).status_code
        == 404
    )

    other_org, other_workspace, other_project = bootstrap(source_asset_client, "source-other")
    assert (
        source_asset_client.get(
            f"{_path(other_org, other_workspace, other_project)}/{asset_id}",
            headers=headers("actor:owner", other_org, other_workspace),
        ).status_code
        == 404
    )

    invalid_headers = {**tenant_headers, "Idempotency-Key": "invalid-source-key"}
    for invalid in [
        _payload(original_filename="../bad.pdf"),
        _payload(original_filename=r"C:\\private\\source.pdf"),
        _payload(original_filename=r"\\\\host\\share\\source.pdf"),
        _payload(original_filename="file://source.pdf"),
        _payload(source_reference="/tmp/source.pdf"),
        _payload(source_reference=r"C:\\private\\source.pdf"),
        _payload(source_reference=r"\\\\host\\share\\source.pdf"),
        _payload(source_reference="file://source.pdf"),
        _payload(source_reference="postgresql://user:secret@localhost/foundation"),
        _payload(source_reference="Bearer sensitive-token"),
        _payload(source_reference="https://example.invalid/file?x-amz-signature=secret"),
        _payload(source_reference="line-one\nline-two"),
        _payload(checksum_value="A" * 64),
        _payload(byte_size=0),
        _payload(byte_size=104857601),
        _payload(media_type="image/png"),
        {**_payload(), "status": "active"},
    ]:
        assert (
            source_asset_client.post(
                _path(organization_id, workspace_id, project_id),
                headers=invalid_headers,
                json=invalid,
            ).status_code
            == 400
        )

    malformed = headers("actor:owner", organization_id, workspace_id)
    malformed["Idempotency-Key"] = "short"
    assert (
        source_asset_client.post(
            _path(organization_id, workspace_id, project_id), headers=malformed, json=_payload()
        ).status_code
        == 400
    )
