import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.app.application.idea_intake_services import IdeaIntakeApplicationService
from services.api.app.application.model_provider import (
    DeterministicFakeProvider,
    ModelRequest,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.config import ApiSettings
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.app.main import create_app
from services.api.tests.test_brief_api import bootstrap, headers


@pytest.fixture
def idea_client(
    test_database_url: str, clean_database: None, tmp_path: Path
) -> Iterator[TestClient]:
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


def _project_root(organization_id: str, workspace_id: str, project_id: str) -> str:
    return (
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    )


def test_create_patch_confirm_idea_intake_creates_brief_and_audit(
    idea_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(idea_client, "idea-main")
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    root = _project_root(organization_id, workspace_id, project_id)

    created = idea_client.post(
        f"{root}/idea-intakes",
        headers=tenant_headers,
        json={
            "idea": "I want to create a cinematic Xiaohongshu video introducing "
            "a new coffee shop for young office workers."
        },
    )

    assert created.status_code == 201, created.text
    intake = created.json()
    assert intake["raw_idea"].startswith("I want to create")
    assert intake["status"] == "structured"
    assert intake["platform"] == "Xiaohongshu"
    assert intake["brief_id"] is None

    patched = idea_client.patch(
        f"{root}/idea-intakes/{intake['id']}",
        headers=tenant_headers,
        json={
            "expected_version": 1,
            "objective": "Introduce the new coffee shop",
            "platform": "Xiaohongshu",
            "audience": "young office workers",
            "duration_seconds": 30,
            "content_type": "short-form video",
            "tone": ["cinematic", "warm"],
            "key_messages": ["A comfortable coffee break near the office"],
            "call_to_action": "Visit this week",
            "constraints": [],
            "must_include": ["coffee shop exterior"],
            "must_avoid": [],
            "assumptions": ["Audience works near the shop."],
            "missing_fields": [],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["version"] == 2

    confirmed = idea_client.post(
        f"{root}/idea-intakes/{intake['id']}/confirm",
        headers=tenant_headers,
        json={"expected_version": 2, "title": "Coffee shop launch"},
    )

    assert confirmed.status_code == 201, confirmed.text
    body = confirmed.json()
    assert body["idea_intake"]["status"] == "confirmed"
    assert body["result"]["brief"]["title"] == "Coffee shop launch"
    assert body["result"]["current_version"]["source_type"] == "idea_intake"
    assert body["result"]["current_version"]["source_reference"] == intake["id"]
    structured = body["result"]["current_version"]["structured_content"]
    assert structured["objective"]["primary_goal"] == "Introduce the new coffee shop"
    assert structured["channels"] == ["social"]

    events = idea_client.get(
        f"{root}/briefs/{body['result']['brief']['id']}/audit-events",
        headers=tenant_headers,
    )
    assert events.status_code == 200
    assert [event["action"] for event in events.json()["items"]] == ["brief.created"]


def test_saved_answer_resolves_its_gap_without_erasing_other_questions(
    idea_client: TestClient,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(idea_client, "idea-gap")
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    root = _project_root(organization_id, workspace_id, project_id)
    created = idea_client.post(
        f"{root}/idea-intakes", headers=tenant_headers, json={"idea": "Create a short film"}
    )
    assert created.status_code == 201
    intake = created.json()
    fields = {
        key: value
        for key, value in intake.items()
        if key
        in {
            "objective",
            "platform",
            "audience",
            "duration_seconds",
            "content_type",
            "tone",
            "key_messages",
            "call_to_action",
            "constraints",
            "must_include",
            "must_avoid",
            "assumptions",
            "missing_fields",
        }
    }
    assert intake["platform"] is None
    saved = idea_client.patch(
        f"{root}/idea-intakes/{intake['id']}",
        headers=tenant_headers,
        json={
            **fields,
            "expected_version": 1,
            "call_to_action": "Visit tomorrow",
            "missing_fields": ["platform", "call_to_action", "proof_points"],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["missing_fields"] == ["platform", "proof_points"]
    assert saved.json()["assumptions"] == intake["assumptions"]
    restored = idea_client.get(f"{root}/idea-intakes/{intake['id']}", headers=tenant_headers)
    assert restored.json() == saved.json()
    confirmed = idea_client.post(
        f"{root}/idea-intakes/{intake['id']}/confirm",
        headers=tenant_headers,
        json={"expected_version": 2},
    )
    assert confirmed.status_code == 201
    content = confirmed.json()["result"]["current_version"]["structured_content"]
    assert content["creative_constraints"]["call_to_action"] == "Visit tomorrow"
    assert content["open_questions"] == ["platform", "proof_points"]


def test_idea_intake_permissions_and_archived_project(
    idea_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id, workspace_id, project_id = bootstrap(idea_client, "idea-auth")
    owner_headers = headers("actor:owner", organization_id, workspace_id)
    viewer = idea_client.post(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
        headers=owner_headers,
        json={"actor_subject": "actor:viewer", "role": "viewer"},
    )
    assert viewer.status_code == 201, viewer.text
    root = _project_root(organization_id, workspace_id, project_id)

    def forbidden_provider_call(*_: object) -> dict[str, object]:
        raise AssertionError("Unauthorized or archived input must not invoke structuring")

    monkeypatch.setattr(
        cast(FastAPI, idea_client.app).state.idea_intake_service,
        "_structure_idea",
        forbidden_provider_call,
    )

    denied = idea_client.post(
        f"{root}/idea-intakes",
        headers=headers("actor:viewer", organization_id, workspace_id),
        json={"idea": "Create a short launch video."},
    )
    assert denied.status_code == 404

    archived = idea_client.post(
        f"{root}/archive",
        headers=owner_headers,
        json={"expected_version": 1},
    )
    assert archived.status_code == 200, archived.text
    blocked = idea_client.post(
        f"{root}/idea-intakes",
        headers=owner_headers,
        json={"idea": "Create a short launch video."},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "project_archived"


@pytest.mark.parametrize("duration", [14, 61])
def test_intake_rejects_unsupported_duration_without_mutating_draft(
    idea_client: TestClient, duration: int
) -> None:
    organization_id, workspace_id, project_id = bootstrap(idea_client, f"duration-{duration}")
    tenant_headers = headers("actor:owner", organization_id, workspace_id)
    root = _project_root(organization_id, workspace_id, project_id)
    created = idea_client.post(
        f"{root}/idea-intakes", headers=tenant_headers, json={"idea": "Create a 30 second film"}
    )
    assert created.status_code == 201
    intake = created.json()
    fields = {
        key: value
        for key, value in intake.items()
        if key
        in {
            "objective",
            "platform",
            "audience",
            "duration_seconds",
            "content_type",
            "tone",
            "key_messages",
            "call_to_action",
            "constraints",
            "must_include",
            "must_avoid",
            "assumptions",
            "missing_fields",
        }
    }
    patched = idea_client.patch(
        f"{root}/idea-intakes/{intake['id']}",
        headers=tenant_headers,
        json={**fields, "expected_version": 1, "duration_seconds": duration},
    )
    assert patched.status_code == 400
    assert patched.json()["error"]["code"] == "invalid_request"
    assert patched.json()["error"]["message"] == "Invalid request"
    recovered = idea_client.get(f"{root}/idea-intakes/{intake['id']}", headers=tenant_headers)
    assert recovered.status_code == 200
    assert recovered.json() == intake


def test_idea_intake_retries_malformed_model_output(
    test_database_url: str,
    clean_database: None,
    tmp_path: Path,
    persistence_session_factory: SessionFactory,
) -> None:
    del clean_database
    provider = _RetryProvider()
    app = create_app(
        ApiSettings(
            app_environment="test",
            database_url=test_database_url,
            source_object_storage_root=str(tmp_path / "objects"),
        )
    )
    app.state.idea_intake_service = IdeaIntakeApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory),
        provider,
    )
    with TestClient(app) as client:
        organization_id, workspace_id, project_id = bootstrap(client, "idea-retry")
        response = client.post(
            f"{_project_root(organization_id, workspace_id, project_id)}/idea-intakes",
            headers=headers("actor:owner", organization_id, workspace_id),
            json={"idea": "Make a 30 second TikTok ad for an AI bookkeeping app."},
        )
    assert response.status_code == 201, response.text
    assert provider.calls == 2


class _RetryProvider(DeterministicFakeProvider):
    def __init__(self) -> None:
        super().__init__(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, "{"))
        self.calls = 0

    def complete(self, request: ModelRequest) -> ProviderOutcome:
        self.calls += 1
        if self.calls == 1:
            return ProviderOutcome(ProviderOutcomeStatus.SUCCESS, "{")
        return ProviderOutcome(
            ProviderOutcomeStatus.SUCCESS,
            json.dumps(
                {
                    "objective": "Make a TikTok ad for an AI bookkeeping app.",
                    "platform": "TikTok",
                    "audience": None,
                    "duration_seconds": 30,
                    "content_type": "short-form ad",
                    "tone": [],
                    "key_messages": ["AI bookkeeping saves time."],
                    "call_to_action": None,
                    "constraints": [],
                    "must_include": [],
                    "must_avoid": [],
                    "assumptions": ["Audience owns or works in a small business."],
                    "missing_fields": ["audience", "call_to_action"],
                }
            ),
        )
