from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from services.api.app.infrastructure.database import SessionFactory
from services.api.tests.test_ingestion_concurrency import _setup


def _row(
    org: object, workspace: object, project: object, brief: object, version: object
) -> dict[str, object]:
    return {
        "id": uuid4(),
        "organization_id": org,
        "workspace_id": workspace,
        "project_id": project,
        "brief_id": brief,
        "brief_version_id": version,
        "operation": "create_version",
        "idempotency_key": f"constraint-{uuid4().hex}",
        "source_type": "api_structured",
        "source_reference": None,
        "payload_digest": "a" * 64,
        "schema_version": "1.0.0",
        "status": "accepted",
        "rejection_code": None,
        "rejection_details": None,
        "submitted_by_actor_subject": "actor:owner",
        "submitted_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
        "correlation_id": "constraint-test",
        "version": 1,
    }


INSERT = text(
    "INSERT INTO brief_ingestions (id, organization_id, workspace_id, project_id, brief_id, "
    "brief_version_id, operation, idempotency_key, source_type, source_reference, payload_digest, "
    "schema_version, status, rejection_code, rejection_details, submitted_by_actor_subject, "
    "submitted_at, completed_at, correlation_id, version) VALUES "
    "(:id, :organization_id, :workspace_id, :project_id, :brief_id, :brief_version_id, :operation, "
    ":idempotency_key, :source_type, :source_reference, :payload_digest, :schema_version, :status, "
    ":rejection_code, :rejection_details, :submitted_by_actor_subject, :submitted_at, "
    ":completed_at, "
    ":correlation_id, :version)"
)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "reserved", "brief_id": "keep"},
        {"status": "reserved", "brief_version_id": "keep"},
        {"status": "reserved", "brief_id": None, "brief_version_id": None, "completed_at": "now"},
        {"status": "reserved", "brief_id": None, "brief_version_id": None, "rejection_code": "bad"},
        {"brief_id": None},
        {"brief_version_id": None},
        {"completed_at": None},
        {"rejection_details": "bad"},
        {"status": "rejected", "brief_id": "keep"},
        {"payload_digest": "not-a-digest"},
        {"operation": "unsupported"},
        {"source_type": "manual"},
        {"schema_version": "2.0.0"},
        {"status": "invalid"},
        {"version": 0},
    ],
)
def test_ingestion_database_checks_reject_invalid_outcomes(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    overrides: dict[str, object],
) -> None:
    del clean_database
    context, project_id, brief_id, version_id = _setup(persistence_session_factory)
    row = _row(context.organization_id, context.workspace_id, project_id, brief_id, version_id)
    for field, value in overrides.items():
        row[field] = (
            row[field] if value == "keep" else datetime.now(UTC) if value == "now" else value
        )
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT, row)


def test_ingestion_database_foreign_keys_and_scoped_unique_constraint(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context_a, project_a, brief_a, version_a = _setup(persistence_session_factory)
    context_b, project_b, brief_b, version_b = _setup(persistence_session_factory)
    del version_a
    base = _row(context_a.organization_id, context_a.workspace_id, project_a, brief_a, version_b)
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT, base)  # Version belongs to another Brief/tenant.

    cross_project = _row(
        context_a.organization_id, context_a.workspace_id, project_b, brief_a, brief_a
    )
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT, cross_project)

    valid = _row(context_a.organization_id, context_a.workspace_id, project_a, brief_a, brief_a)
    valid["brief_version_id"] = _setup(persistence_session_factory)[3]
    # The generated version is not attached to the selected Brief, proving the composite FK too.
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT, valid)

    accepted = _row(
        context_b.organization_id, context_b.workspace_id, project_b, brief_b, version_b
    )
    accepted["idempotency_key"] = "scoped-unique-key"
    with database_engine.begin() as connection:
        connection.execute(INSERT, accepted)
    duplicate = dict(accepted, id=uuid4())
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT, duplicate)
