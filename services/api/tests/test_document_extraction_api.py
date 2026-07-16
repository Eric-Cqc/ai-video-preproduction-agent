from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from services.api.app.config import ApiSettings
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, headers
from services.api.tests.test_source_object_api import (
    _assets_path,
    _create_target,
    _upload_headers,
    _upload_path,
)


@pytest.fixture
def extraction_client(
    test_database_url: str, clean_database: None, tmp_path: Path
) -> Iterator[TestClient]:
    del clean_database
    with TestClient(
        create_app(
            ApiSettings(
                app_environment="test",
                database_url=test_database_url,
                source_object_storage_root=str(tmp_path / "extraction-objects"),
            )
        )
    ) as client:
        yield client


def _prepare(
    client: TestClient, content: bytes, label: str, media_type: str
) -> tuple[tuple[str, ...], str]:
    target = _create_target(client, content, label, media_type)
    upload = client.post(
        _upload_path(target),
        headers=_upload_headers(target, f"{label}-upload-key"),
        content=content,
    )
    assert upload.status_code == 201, upload.text
    path = _upload_path(target).removesuffix("/uploads") + "/extractions"
    return target, path


@pytest.mark.parametrize(
    ("media_type", "content", "expected"),
    [
        ("text/plain", b"alpha\r\nbeta", "alpha\nbeta"),
        ("text/csv", b'b,a\r\n"x,y",z\r\n', 'b,a\n"x,y",z\n'),
        ("application/json", b'{"b":2,"a":1}', '{"a":1,"b":2}'),
    ],
)
def test_create_replay_get_and_deterministic_formats(
    extraction_client: TestClient,
    database_engine: Engine,
    media_type: str,
    content: bytes,
    expected: str,
) -> None:
    target, path = _prepare(
        extraction_client, content, f"extract-{media_type.split('/')[-1]}", media_type
    )
    org, workspace, *_ = target
    request_headers = {
        **headers("actor:owner", org, workspace),
        "Idempotency-Key": f"extract-key-{media_type.split('/')[-1]}",
    }
    created = extraction_client.post(path, headers=request_headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["extraction"]["extracted_document"]["text"] == expected
    assert body["extraction"]["schema_version"] == "1.0.0"
    for forbidden in ("source_checksum", "options_digest", "extraction_checksum"):
        assert forbidden not in created.text

    replay = extraction_client.post(path, headers=request_headers)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    extraction_id = body["extraction"]["id"]
    fetched = extraction_client.get(
        f"{path}/{extraction_id}", headers=headers("actor:owner", org, workspace)
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == extraction_id

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM document_extractions), "
                "(SELECT count(*) FROM document_extraction_operations), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='document_extraction.completed')"
            )
        ).one()
        payload = connection.scalar(
            text("SELECT payload FROM audit_events WHERE action='document_extraction.completed'")
        )
    assert counts == (1, 1, 1)
    assert expected not in str(payload)


def test_unsupported_media_missing_key_and_cross_tenant_are_safe(
    extraction_client: TestClient,
) -> None:
    content = b"%PDF-not-parsed"
    target, path = _prepare(extraction_client, content, "extract-pdf", "application/pdf")
    org, workspace, *_ = target
    tenant_headers = headers("actor:owner", org, workspace)
    assert extraction_client.post(path, headers=tenant_headers).status_code == 400
    unsupported = extraction_client.post(
        path, headers={**tenant_headers, "Idempotency-Key": "unsupported-parser-key"}
    )
    assert unsupported.status_code == 400
    assert "not supported" in unsupported.json()["error"]["message"]

    other_org, other_workspace, _ = bootstrap(extraction_client, "other-extraction-tenant")
    inaccessible = extraction_client.post(
        path,
        headers={
            **headers("actor:owner", other_org, other_workspace),
            "Idempotency-Key": "cross-tenant-extract",
        },
    )
    assert inaccessible.status_code == 404


def test_replay_survives_later_archive_and_new_key_conflicts(
    extraction_client: TestClient,
) -> None:
    target, path = _prepare(extraction_client, b"archive me", "extract-archive", "text/plain")
    org, workspace, project, asset, version = target
    tenant_headers = headers("actor:owner", org, workspace)
    key_headers = {**tenant_headers, "Idempotency-Key": "archive-extraction-key"}
    created = extraction_client.post(path, headers=key_headers)
    assert created.status_code == 201
    archive = extraction_client.post(
        f"{_assets_path(org, workspace, project)}/{asset}/archive",
        headers={**tenant_headers, "Idempotency-Key": "archive-after-extraction"},
        json={"expected_source_asset_version": 1, "expected_current_version_id": version},
    )
    assert archive.status_code == 200
    assert extraction_client.post(path, headers=key_headers).status_code == 200
    fresh = extraction_client.post(
        path, headers={**tenant_headers, "Idempotency-Key": "fresh-after-archive"}
    )
    assert fresh.status_code == 409
