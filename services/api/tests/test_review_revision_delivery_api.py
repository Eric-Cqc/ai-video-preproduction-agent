from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from services.api.app.infrastructure.database import SessionFactory
from services.api.tests.test_brief_api import headers
from services.api.tests.test_visual_planning_persistence import (
    _insert_script_graph,
    _seed_project,
)
from services.api.tests.test_visual_planning_services import _make_script_usable


@pytest.fixture
def delivery_client(
    test_database_url: str, clean_database: None, tmp_path: Path
) -> Iterator[TestClient]:
    from services.api.app.config import ApiSettings
    from services.api.app.main import create_app

    del clean_database
    app = create_app(
        ApiSettings(
            app_environment="test",
            database_url=test_database_url,
            source_object_storage_root=str(tmp_path / "delivery-objects"),
        )
    )
    with TestClient(app) as client:
        yield client


def test_review_package_export_api_replay_and_opaque_404(
    delivery_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
) -> None:
    seed = _seed_project(persistence_session_factory, name="Stage 13 API")
    graph = _insert_script_graph(database_engine, seed, "api")
    _make_script_usable(database_engine, graph.script_version_id)
    owner_headers = headers(
        seed.context.actor_subject,
        str(seed.context.organization_id),
        str(seed.context.workspace_id),
    )
    root = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/"
        f"{seed.context.workspace_id}/projects/{seed.project_id}"
    )
    board = delivery_client.post(
        f"{root}/scripts/{graph.script_version_id}/storyboards",
        headers={**owner_headers, "Idempotency-Key": "api-stage13-board"},
        json={},
    )
    assert board.status_code == 201, board.text
    board_id = board.json()["version"]["id"]
    shot = delivery_client.post(
        f"{root}/storyboards/{board_id}/shot-plans",
        headers={**owner_headers, "Idempotency-Key": "api-stage13-shot"},
        json={},
    )
    assert shot.status_code == 201, shot.text
    shot_id = shot.json()["version"]["id"]
    review = delivery_client.post(
        f"{root}/planning-reviews",
        headers={**owner_headers, "Idempotency-Key": "api-stage13-review"},
        json={
            "artifact_type": "planning_bundle",
            "script_version_id": str(graph.script_version_id),
            "storyboard_version_id": board_id,
            "shot_plan_version_id": shot_id,
            "outcome": "approved",
            "summary": "Approved for delivery.",
            "requested_changes": {},
        },
    )
    assert review.status_code == 201, review.text
    review_replay = delivery_client.post(
        f"{root}/planning-reviews",
        headers={**owner_headers, "Idempotency-Key": "api-stage13-review"},
        json={
            "artifact_type": "planning_bundle",
            "script_version_id": str(graph.script_version_id),
            "storyboard_version_id": board_id,
            "shot_plan_version_id": shot_id,
            "outcome": "approved",
            "summary": "Approved for delivery.",
            "requested_changes": {},
        },
    )
    assert review_replay.status_code == 200
    assert review_replay.json()["replayed"] is True
    package = delivery_client.post(
        f"{root}/delivery-packages",
        headers={**owner_headers, "Idempotency-Key": "api-stage13-package"},
        json={
            "script_version_id": str(graph.script_version_id),
            "storyboard_version_id": board_id,
            "shot_plan_version_id": shot_id,
            "approval_review_id": review.json()["review"]["id"],
        },
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["package"]["id"]
    exported = delivery_client.post(
        f"{root}/delivery-packages/{package_id}/exports",
        headers={**owner_headers, "Idempotency-Key": "api-stage13-export"},
        json={"format": "manifest.json"},
    )
    assert exported.status_code == 201, exported.text
    export_id = exported.json()["export"]["id"]
    downloaded = delivery_client.get(f"{root}/delivery-exports/{export_id}", headers=owner_headers)
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/json")
    assert downloaded.json()["schema_version"] == "delivery-package-v1"
    assert "request_digest" not in exported.text
    assert "storage_key" not in exported.text


def test_missing_delivery_export_is_rejected_before_streaming(
    delivery_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
) -> None:
    seed = _seed_project(persistence_session_factory, name="Stage 20 missing export")
    graph = _insert_script_graph(database_engine, seed, "missing-export")
    _make_script_usable(database_engine, graph.script_version_id)
    owner_headers = headers(
        seed.context.actor_subject,
        str(seed.context.organization_id),
        str(seed.context.workspace_id),
    )
    root = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/"
        f"{seed.context.workspace_id}/projects/{seed.project_id}"
    )
    board = delivery_client.post(
        f"{root}/scripts/{graph.script_version_id}/storyboards",
        headers={**owner_headers, "Idempotency-Key": "missing-export-board"},
        json={},
    )
    assert board.status_code == 201, board.text
    board_id = board.json()["version"]["id"]
    shot = delivery_client.post(
        f"{root}/storyboards/{board_id}/shot-plans",
        headers={**owner_headers, "Idempotency-Key": "missing-export-shot"},
        json={},
    )
    assert shot.status_code == 201, shot.text
    shot_id = shot.json()["version"]["id"]
    review = delivery_client.post(
        f"{root}/planning-reviews",
        headers={**owner_headers, "Idempotency-Key": "missing-export-review"},
        json={
            "artifact_type": "planning_bundle",
            "script_version_id": str(graph.script_version_id),
            "storyboard_version_id": board_id,
            "shot_plan_version_id": shot_id,
            "outcome": "approved",
            "summary": "Approved for missing-object test.",
            "requested_changes": {},
        },
    )
    assert review.status_code == 201, review.text
    package = delivery_client.post(
        f"{root}/delivery-packages",
        headers={**owner_headers, "Idempotency-Key": "missing-export-package"},
        json={
            "script_version_id": str(graph.script_version_id),
            "storyboard_version_id": board_id,
            "shot_plan_version_id": shot_id,
            "approval_review_id": review.json()["review"]["id"],
        },
    )
    assert package.status_code == 201, package.text
    exported = delivery_client.post(
        f"{root}/delivery-packages/{package.json()['package']['id']}/exports",
        headers={**owner_headers, "Idempotency-Key": "missing-export-file"},
        json={"format": "manifest.json"},
    )
    assert exported.status_code == 201, exported.text
    export_id = exported.json()["export"]["id"]
    with database_engine.connect() as connection:
        storage_key = connection.scalar(
            text("SELECT storage_key FROM delivery_export_files WHERE id=:id"),
            {"id": export_id},
        )
    cast(FastAPI, delivery_client.app).state.review_revision_delivery_service.storage.delete(
        storage_key
    )

    missing = delivery_client.get(f"{root}/delivery-exports/{export_id}", headers=owner_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "resource_not_found"


def test_review_api_rejects_mass_assignment_and_wrong_tenant(
    delivery_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
) -> None:
    seed = _seed_project(persistence_session_factory, name="Stage 13 API scope")
    graph = _insert_script_graph(database_engine, seed, "scope-api")
    _make_script_usable(database_engine, graph.script_version_id)
    owner_headers = headers(
        seed.context.actor_subject,
        str(seed.context.organization_id),
        str(seed.context.workspace_id),
    )
    root = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/"
        f"{seed.context.workspace_id}/projects/{seed.project_id}"
    )
    invalid = delivery_client.post(
        f"{root}/planning-reviews",
        headers={**owner_headers, "Idempotency-Key": "api-invalid"},
        json={
            "artifact_type": "script",
            "script_version_id": str(graph.script_version_id),
            "outcome": "approved",
            "summary": "Approved.",
            "requested_changes": {},
            "status": "accepted",
        },
    )
    assert invalid.status_code == 400
    wrong = delivery_client.get(
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/"
        f"{seed.context.workspace_id}/projects/{seed.project_id}/planning-reviews/"
        "00000000-0000-0000-0000-000000000000",
        headers=owner_headers,
    )
    assert wrong.status_code == 404


def test_cancel_revision_api_replay_digest_and_audit(
    delivery_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
) -> None:
    seed = _seed_project(persistence_session_factory, name="Stage 20 cancellation API")
    graph = _insert_script_graph(database_engine, seed, "cancel-api")
    _make_script_usable(database_engine, graph.script_version_id)
    owner_headers = headers(
        seed.context.actor_subject,
        str(seed.context.organization_id),
        str(seed.context.workspace_id),
    )
    root = (
        f"/api/v1/organizations/{seed.context.organization_id}/workspaces/"
        f"{seed.context.workspace_id}/projects/{seed.project_id}"
    )
    review_payload = {
        "artifact_type": "script",
        "script_version_id": str(graph.script_version_id),
        "outcome": "revision_requested",
        "summary": "Request a bounded revision.",
        "requested_changes": {"mode": "valid"},
    }
    review = delivery_client.post(
        f"{root}/planning-reviews",
        headers={**owner_headers, "Idempotency-Key": "cancel-api-review-1"},
        json=review_payload,
    )
    assert review.status_code == 201, review.text
    request_id = review.json()["revision_request"]["id"]
    cancel_path = f"{root}/revision-requests/{request_id}/cancel"
    cancel = delivery_client.post(
        cancel_path,
        headers={**owner_headers, "Idempotency-Key": "cancel-api-key"},
    )
    assert cancel.status_code == 201, cancel.text
    assert cancel.json()["revision_request"]["status"] == "cancelled"
    assert cancel.json()["replayed"] is False

    replay = delivery_client.post(
        cancel_path,
        headers={**owner_headers, "Idempotency-Key": "cancel-api-key"},
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["revision_request"]["id"] == request_id

    second_review = delivery_client.post(
        f"{root}/planning-reviews",
        headers={**owner_headers, "Idempotency-Key": "cancel-api-review-2"},
        json={**review_payload, "summary": "Request another bounded revision."},
    )
    assert second_review.status_code == 201, second_review.text
    second_request_id = second_review.json()["revision_request"]["id"]
    digest_mismatch = delivery_client.post(
        f"{root}/revision-requests/{second_request_id}/cancel",
        headers={**owner_headers, "Idempotency-Key": "cancel-api-key"},
    )
    assert digest_mismatch.status_code == 409
    assert digest_mismatch.json()["error"]["code"] == "idempotency_conflict"

    with database_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events "
                    "WHERE aggregate_id = :request_id AND action = 'planning_revision.cancelled'"
                ),
                {"request_id": request_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT operation FROM delivery_operations "
                    "WHERE idempotency_key = 'cancel-api-key'"
                )
            )
            == "cancel_revision_request"
        )
