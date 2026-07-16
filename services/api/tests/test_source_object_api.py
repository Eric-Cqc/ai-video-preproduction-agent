import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from services.api.app.config import ApiSettings
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, headers


@pytest.fixture
def source_object_client(
    test_database_url: str, clean_database: None, tmp_path: Path
) -> Iterator[TestClient]:
    del clean_database
    settings = ApiSettings(
        app_environment="test",
        database_url=test_database_url,
        source_object_storage_root=str(tmp_path / "objects"),
    )
    with TestClient(create_app(settings)) as client:
        yield client


def _assets_path(org: str, workspace: str, project: str) -> str:
    return f"/api/v1/organizations/{org}/workspaces/{workspace}/projects/{project}/source-assets"


def _create_target(client: TestClient, content: bytes, label: str = "upload") -> tuple[str, ...]:
    org, workspace, project = bootstrap(client, label)
    request_headers = headers("actor:owner", org, workspace)
    request_headers["Idempotency-Key"] = f"{label}-metadata-key"
    response = client.post(
        _assets_path(org, workspace, project),
        headers=request_headers,
        json={
            "display_name": "Uploaded source",
            "original_filename": "../../never-a-path.txt",
            "media_type": "text/plain",
            "byte_size": len(content),
            "checksum_algorithm": "sha256",
            "checksum_value": hashlib.sha256(content).hexdigest(),
            "source_type": "api_declared",
            "source_reference": None,
            "external_record_id": None,
            "declared_created_at": None,
        },
    )
    # The filename guard deliberately rejects traversal; retry with a safe display filename.
    assert response.status_code == 400
    response = client.post(
        _assets_path(org, workspace, project),
        headers={**request_headers, "Idempotency-Key": f"{label}-metadata-key-safe"},
        json={
            "display_name": "Uploaded source",
            "original_filename": "customer-source.txt",
            "media_type": "text/plain",
            "byte_size": len(content),
            "checksum_algorithm": "sha256",
            "checksum_value": hashlib.sha256(content).hexdigest(),
            "source_type": "api_declared",
            "source_reference": None,
            "external_record_id": None,
            "declared_created_at": None,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return org, workspace, project, body["source_asset"]["id"], body["current_version"]["id"]


def _upload_path(values: tuple[str, ...]) -> str:
    org, workspace, project, asset, version = values
    return f"{_assets_path(org, workspace, project)}/{asset}/versions/{version}/uploads"


def _upload_headers(values: tuple[str, ...], key: str) -> dict[str, str]:
    org, workspace, *_ = values
    return {
        **headers("actor:owner", org, workspace),
        "Idempotency-Key": key,
        "Content-Type": "application/octet-stream",
    }


def test_upload_replay_read_and_safe_response(
    source_object_client: TestClient, database_engine: Engine
) -> None:
    content = b"verified source bytes\n"
    target = _create_target(source_object_client, content)
    request_headers = _upload_headers(target, "binary-upload-key-0001")

    created = source_object_client.post(
        _upload_path(target), headers=request_headers, content=content
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["replayed"] is False
    assert body["source_object"]["observed_byte_size"] == len(content)
    for forbidden in ("storage_key", "request_digest", "idempotency_key", "checksum_value"):
        assert forbidden not in created.text

    replay = source_object_client.post(
        _upload_path(target), headers=request_headers, content=content
    )
    assert replay.status_code == 200
    assert replay.json()["source_object"]["id"] == body["source_object"]["id"]
    assert replay.json()["replayed"] is True

    object_path = _upload_path(target).removesuffix("/uploads") + "/object"
    assert source_object_client.get(object_path, headers=request_headers).status_code == 200
    downloaded = source_object_client.get(object_path + "/content", headers=request_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == content

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_objects), "
                "(SELECT count(*) FROM source_object_uploads), "
                "(SELECT count(*) FROM audit_events WHERE action = 'source_object.uploaded')"
            )
        ).one()
        payload = connection.scalar(
            text("SELECT payload FROM audit_events WHERE action = 'source_object.uploaded'")
        )
    assert counts == (1, 1, 1)
    assert isinstance(payload, dict)
    assert "checksum" not in str(payload).lower()
    assert "filename" not in str(payload).lower()


def test_same_key_different_bytes_is_conflict(source_object_client: TestClient) -> None:
    content = b"canonical bytes"
    target = _create_target(source_object_client, content, "upload-conflict")
    request_headers = _upload_headers(target, "binary-upload-conflict")
    assert (
        source_object_client.post(
            _upload_path(target), headers=request_headers, content=content
        ).status_code
        == 201
    )
    conflict = source_object_client.post(
        _upload_path(target), headers=request_headers, content=b"different bytes"
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert "binary-upload-conflict" not in conflict.text


@pytest.mark.parametrize("content", [b"", b"wrong"])
def test_empty_or_mismatched_upload_rolls_back(
    source_object_client: TestClient, database_engine: Engine, content: bytes
) -> None:
    target = _create_target(source_object_client, b"expected", f"mismatch-{len(content)}")
    response = source_object_client.post(
        _upload_path(target),
        headers=_upload_headers(target, f"binary-mismatch-{len(content):04d}"),
        content=content,
    )
    assert response.status_code == 400
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM source_objects")) == 0
        assert connection.scalar(text("SELECT count(*) FROM source_object_uploads")) == 0


def test_upload_requires_key_type_and_tenant_scope(source_object_client: TestClient) -> None:
    content = b"tenant bytes"
    target = _create_target(source_object_client, content, "upload-scope")
    base_headers = _upload_headers(target, "binary-upload-scope")
    assert (
        source_object_client.post(
            _upload_path(target),
            headers={k: v for k, v in base_headers.items() if k != "Idempotency-Key"},
            content=content,
        ).status_code
        == 400
    )
    assert (
        source_object_client.post(
            _upload_path(target),
            headers={**base_headers, "Content-Type": "text/plain"},
            content=content,
        ).status_code
        == 400
    )

    other_org, other_workspace, _ = bootstrap(source_object_client, "other-upload-tenant")
    inaccessible = source_object_client.post(
        _upload_path(target),
        headers={
            **headers("actor:owner", other_org, other_workspace),
            "Idempotency-Key": "cross-tenant-upload",
            "Content-Type": "application/octet-stream",
        },
        content=content,
    )
    assert inaccessible.status_code == 404


def test_stream_limit_is_enforced_without_persisting(
    test_database_url: str, clean_database: None, tmp_path: Path, database_engine: Engine
) -> None:
    del clean_database
    settings = ApiSettings(
        app_environment="test",
        database_url=test_database_url,
        source_object_storage_root=str(tmp_path / "limited"),
        api_max_upload_bytes=4,
    )
    with TestClient(create_app(settings)) as client:
        target = _create_target(client, b"12345", "upload-limit")
        response = client.post(
            _upload_path(target),
            headers=_upload_headers(target, "binary-upload-limit"),
            content=b"12345",
        )
    assert response.status_code == 413
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM source_objects")) == 0
