import hashlib
import io
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from services.api.app.config import ApiSettings
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, fixture, headers


@pytest.fixture
def rc_client(test_database_url: str, clean_database: None, tmp_path: Path) -> Iterator[TestClient]:
    del clean_database
    app = create_app(
        ApiSettings(
            app_environment="test",
            database_url=test_database_url,
            source_object_storage_root=str(tmp_path / "objects"),
        )
    )
    with TestClient(app) as client:
        yield client


def test_complete_rc_golden_path_uses_http_persistence_and_storage(
    rc_client: TestClient,
    database_engine: Engine,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(rc_client, "rc-golden")
    actor_headers = headers("actor:owner", organization_id, workspace_id)
    root = (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    )
    source = json.dumps(fixture("valid-structured-brief-v1.json"), sort_keys=True).encode()
    digest = hashlib.sha256(source).hexdigest()

    asset_response = rc_client.post(
        f"{root}/source-assets",
        headers={**actor_headers, "Idempotency-Key": "rc-source-asset"},
        json={
            "display_name": "rc-brief.json",
            "original_filename": "rc-brief.json",
            "media_type": "application/json",
            "byte_size": len(source),
            "checksum_algorithm": "sha256",
            "checksum_value": digest,
            "source_type": "api_declared",
        },
    )
    assert asset_response.status_code == 201, asset_response.text
    asset = asset_response.json()
    asset_id = asset["source_asset"]["id"]
    version_id = asset["current_version"]["id"]
    replay = rc_client.post(
        f"{root}/source-assets",
        headers={**actor_headers, "Idempotency-Key": "rc-source-asset"},
        json={
            "display_name": "rc-brief.json",
            "original_filename": "rc-brief.json",
            "media_type": "application/json",
            "byte_size": len(source),
            "checksum_algorithm": "sha256",
            "checksum_value": digest,
            "source_type": "api_declared",
        },
    )
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    conflict = rc_client.post(
        f"{root}/source-assets",
        headers={**actor_headers, "Idempotency-Key": "rc-source-asset"},
        json={
            "display_name": "changed.json",
            "original_filename": "rc-brief.json",
            "media_type": "application/json",
            "byte_size": len(source),
            "checksum_algorithm": "sha256",
            "checksum_value": digest,
            "source_type": "api_declared",
        },
    )
    assert conflict.status_code == 409

    upload_path = f"{root}/source-assets/{asset_id}/versions/{version_id}/uploads"
    uploaded = rc_client.post(
        upload_path,
        headers={
            **actor_headers,
            "Idempotency-Key": "rc-upload-object",
            "Content-Type": "application/octet-stream",
        },
        content=source,
    )
    assert uploaded.status_code == 201, uploaded.text
    extraction = rc_client.post(
        f"{root}/source-assets/{asset_id}/versions/{version_id}/extractions",
        headers={**actor_headers, "Idempotency-Key": "rc-parse-document"},
        json={},
    )
    assert extraction.status_code == 201, extraction.text
    extraction_id = extraction.json()["extraction"]["id"]
    run = rc_client.post(
        f"{root}/source-assets/{asset_id}/versions/{version_id}/extractions/"
        f"{extraction_id}/brief-extraction-runs",
        headers=actor_headers,
        json={},
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["run_id"]
    candidate = rc_client.get(
        f"{root}/brief-extraction-runs/{run_id}/candidate", headers=actor_headers
    ).json()["candidate"]
    accepted = rc_client.post(
        f"{root}/brief-extraction-runs/{run_id}/accept",
        headers={**actor_headers, "Idempotency-Key": "rc-accept-brief"},
        json={"accepted_content": candidate, "title": "RC Brief"},
    )
    assert accepted.status_code == 201, accepted.text
    brief_id = accepted.json()["brief_id"]
    brief_version_id = accepted.json()["brief_version_id"]

    concepts = rc_client.post(
        f"{root}/briefs/{brief_id}/versions/{brief_version_id}/concept-runs",
        headers={**actor_headers, "Idempotency-Key": "rc-generate-concepts"},
        json={},
    )
    assert concepts.status_code == 201, concepts.text
    concept_body = concepts.json()
    assert len(concept_body["candidates"]) == 3
    run_id = concept_body["run"]["id"]
    candidate_id = concept_body["candidates"][0]["id"]
    selected = rc_client.post(
        f"{root}/concept-runs/{run_id}/candidates/{candidate_id}/select",
        headers={**actor_headers, "Idempotency-Key": "rc-select-concept"},
        json={},
    )
    assert selected.status_code == 201, selected.text
    script = rc_client.post(
        f"{root}/concept-runs/{run_id}/scripts",
        headers={**actor_headers, "Idempotency-Key": "rc-generate-script"},
        json={},
    )
    assert script.status_code == 201, script.text
    script_id = script.json()["script_version_id"]
    storyboard = rc_client.post(
        f"{root}/scripts/{script_id}/storyboards",
        headers={**actor_headers, "Idempotency-Key": "rc-generate-storyboard"},
        json={"provider_mode": "valid"},
    )
    assert storyboard.status_code == 201, storyboard.text
    storyboard_id = storyboard.json()["version"]["id"]
    shots = rc_client.post(
        f"{root}/storyboards/{storyboard_id}/shot-plans",
        headers={**actor_headers, "Idempotency-Key": "rc-generate-shots"},
        json={"provider_mode": "valid"},
    )
    assert shots.status_code == 201, shots.text
    shot_plan_id = shots.json()["version"]["id"]
    review = rc_client.post(
        f"{root}/planning-reviews",
        headers={**actor_headers, "Idempotency-Key": "rc-approve-bundle"},
        json={
            "artifact_type": "planning_bundle",
            "script_version_id": script_id,
            "storyboard_version_id": storyboard_id,
            "shot_plan_version_id": shot_plan_id,
            "outcome": "approved",
            "summary": "RC approval",
            "requested_changes": {},
        },
    )
    assert review.status_code == 201, review.text
    review_id = review.json()["review"]["id"]
    package = rc_client.post(
        f"{root}/delivery-packages",
        headers={**actor_headers, "Idempotency-Key": "rc-create-delivery"},
        json={
            "script_version_id": script_id,
            "storyboard_version_id": storyboard_id,
            "shot_plan_version_id": shot_plan_id,
            "approval_review_id": review_id,
        },
    )
    assert package.status_code == 201, package.text
    package_body = package.json()["package"]
    assert package_body["script_version_id"] == script_id
    package_id = package_body["id"]
    exported = rc_client.post(
        f"{root}/delivery-packages/{package_id}/exports",
        headers={**actor_headers, "Idempotency-Key": "rc-export-zip"},
        json={"format": "delivery-package.zip"},
    )
    assert exported.status_code == 201, exported.text
    export_body = exported.json()["export"]
    downloaded = rc_client.get(
        f"{root}/delivery-exports/{export_body['id']}", headers=actor_headers
    )
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == export_body["checksum"]
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert "manifest.json" in archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["schema_version"] == "delivery-package-v1"

    viewer = "actor:rc-viewer"
    assert (
        rc_client.post(
            f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
            headers=actor_headers,
            json={"actor_subject": viewer, "role": "viewer"},
        ).status_code
        == 201
    )
    denied = rc_client.post(
        f"{root}/delivery-packages",
        headers={
            **headers(viewer, organization_id, workspace_id),
            "Idempotency-Key": "rc-viewer-denied",
        },
        json={
            "script_version_id": script_id,
            "storyboard_version_id": storyboard_id,
            "shot_plan_version_id": shot_plan_id,
            "approval_review_id": review_id,
        },
    )
    assert denied.status_code == 403

    other_organization, other_workspace, _ = bootstrap(rc_client, "rc-other-tenant")
    cross_tenant = rc_client.get(
        f"/api/v1/organizations/{other_organization}/workspaces/{other_workspace}"
        f"/projects/{project_id}/delivery-exports/{export_body['id']}",
        headers=headers("actor:owner", other_organization, other_workspace),
    )
    assert cross_tenant.status_code == 404

    operation_tables = (
        "source_asset_operations",
        "source_object_uploads",
        "document_extraction_operations",
        "creative_generation_operations",
        "visual_planning_operations",
        "delivery_operations",
    )
    with database_engine.connect() as connection:
        for table in operation_tables:
            count = connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE status = 'reserved'")
            ).scalar_one()
            assert count == 0, table
