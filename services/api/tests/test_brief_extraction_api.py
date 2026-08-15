from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from services.api.app.application.context import TenantContext
from services.api.app.application.model_provider import (
    DeterministicFakeProvider,
    ModelRequest,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.config import ApiSettings
from services.api.app.domain import (
    BriefExtractionOperation,
    BriefExtractionOperationStatus,
    BriefExtractionOperationType,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.app.main import create_app
from services.api.tests.test_brief_api import headers
from services.api.tests.test_brief_extraction_foundation import FIXTURES, _source


class _CountingProvider(DeterministicFakeProvider):
    def __init__(self) -> None:
        super().__init__(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _valid_output()))
        self.calls = 0

    def complete(self, request: ModelRequest) -> ProviderOutcome:
        self.calls += 1
        return super().complete(request)


def _valid_output() -> str:
    return (FIXTURES / "valid-structured-brief-v1.json").read_text()


def _app(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


@pytest.fixture
def extraction_client(
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


def _target(
    session_factory: SessionFactory, tmp_path: Path
) -> tuple[TenantContext, UUID, UUID, UUID, UUID, str]:
    context, project_id, asset_id, version_id, extraction_id = _source(session_factory, tmp_path)
    path = (
        f"/api/v1/organizations/{context.organization_id}/workspaces/{context.workspace_id}"
        f"/projects/{project_id}/source-assets/{asset_id}/versions/{version_id}"
        f"/extractions/{extraction_id}/brief-extraction-runs"
    )
    return context, project_id, asset_id, version_id, extraction_id, path


def _request_headers(
    context: TenantContext, *, key: str | None = None, actor: str | None = None
) -> dict[str, str]:
    result = headers(
        actor or context.actor_subject,
        str(context.organization_id),
        str(context.workspace_id),
    )
    if key is not None:
        result["Idempotency-Key"] = key
    return result


def _reserve_operation(
    session_factory: SessionFactory,
    context: TenantContext,
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    document_extraction_id: UUID,
    key: str,
) -> None:
    operation = BriefExtractionOperation(
        id=uuid4(),
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        project_id=project_id,
        source_asset_id=source_asset_id,
        source_asset_version_id=source_asset_version_id,
        document_extraction_id=document_extraction_id,
        operation=BriefExtractionOperationType.BRIEF_EXTRACTION,
        run_id=None,
        idempotency_key=key,
        request_digest="f" * 64,
        status=BriefExtractionOperationStatus.RESERVED,
        submitted_by_actor_subject=context.actor_subject,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        correlation_id="brief-extraction-test",
        version=1,
    )
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert uow.brief_extraction_operations.reserve(operation) is not None


def test_brief_extraction_idempotency_replays_run_without_provider_or_audit(
    extraction_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    app = _app(extraction_client)
    context, _, _, _, _, path = _target(persistence_session_factory, tmp_path)
    provider = _CountingProvider()
    app.state.brief_extraction_service.provider = provider
    request_headers = _request_headers(context, key="brief-run-key")

    first = extraction_client.post(path, headers=request_headers)
    replay = extraction_client.post(path, headers=request_headers)

    assert first.status_code == 201, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert provider.calls == 1
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_extraction_operations), "
                "(SELECT count(*) FROM brief_extraction_runs), "
                "(SELECT count(*) FROM brief_extraction_attempts), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='brief_extraction.completed')"
            )
        ).one()
    assert tuple(counts) == (1, 1, 1, 1)


def test_brief_extraction_idempotency_digest_mismatch_is_conflict(
    extraction_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    app = _app(extraction_client)
    context, project_id, asset_id, version_id, extraction_id, path = _target(
        persistence_session_factory, tmp_path
    )
    provider = _CountingProvider()
    app.state.brief_extraction_service.provider = provider
    _reserve_operation(
        persistence_session_factory,
        context,
        project_id,
        asset_id,
        version_id,
        extraction_id,
        "brief-digest-key",
    )

    response = extraction_client.post(
        path, headers=_request_headers(context, key="brief-digest-key")
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "idempotency_conflict"
    assert provider.calls == 0
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_extraction_operations), "
                "(SELECT count(*) FROM brief_extraction_runs), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='brief_extraction.completed')"
            )
        ).one()
    assert tuple(counts) == (1, 0, 0)


def test_brief_extraction_without_header_preserves_non_idempotent_behavior(
    extraction_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    app = _app(extraction_client)
    context, _, _, _, _, path = _target(persistence_session_factory, tmp_path)
    provider = _CountingProvider()
    app.state.brief_extraction_service.provider = provider
    owner_headers = _request_headers(context)

    first = extraction_client.post(path, headers=owner_headers)
    second = extraction_client.post(path, headers=owner_headers)
    invalid_key = extraction_client.post(
        path, headers={**owner_headers, "Idempotency-Key": "short"}
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert (
        first.json().keys()
        == second.json().keys()
        == {
            "run_id",
            "status",
            "candidate_available",
        }
    )
    assert first.json()["run_id"] != second.json()["run_id"]
    assert invalid_key.status_code == 400, invalid_key.text
    assert provider.calls == 2
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_extraction_operations), "
                "(SELECT count(*) FROM brief_extraction_runs), "
                "(SELECT count(*) FROM brief_extraction_attempts), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='brief_extraction.completed')"
            )
        ).one()
    assert tuple(counts) == (0, 2, 2, 2)


def test_brief_extraction_valid_key_does_not_bypass_authorization(
    extraction_client: TestClient,
    persistence_session_factory: SessionFactory,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    app = _app(extraction_client)
    context, project_id, _, _, _, path = _target(persistence_session_factory, tmp_path)
    provider = _CountingProvider()
    app.state.brief_extraction_service.provider = provider
    key = "brief-auth-key"
    owner_headers = _request_headers(context, key=key)
    first = extraction_client.post(path, headers=owner_headers)
    assert first.status_code == 201, first.text

    viewer = "actor:brief-viewer"
    membership = extraction_client.post(
        f"/api/v1/organizations/{context.organization_id}/workspaces/"
        f"{context.workspace_id}/memberships",
        headers=_request_headers(context),
        json={"actor_subject": viewer, "role": "viewer"},
    )
    denied = extraction_client.post(path, headers=_request_headers(context, key=key, actor=viewer))

    assert membership.status_code == 201, membership.text
    assert denied.status_code == 404, denied.text
    assert provider.calls == 1
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_extraction_operations), "
                "(SELECT count(*) FROM brief_extraction_runs), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='brief_extraction.completed')"
            )
        ).one()
    assert tuple(counts) == (1, 1, 1)
