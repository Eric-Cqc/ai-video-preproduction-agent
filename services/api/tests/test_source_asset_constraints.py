from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from services.api.app.application.context import ActorContext, OrganizationContext, TenantContext
from services.api.app.application.errors import ResourceConflict
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import BriefIngestionSourceAsset, BriefIngestionSourceAssetRelationType
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.repositories import (
    SqlAlchemyBriefIngestionSourceAssetRepository,
)
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_ingestion_concurrency import _setup as _setup_brief
from services.api.tests.test_ingestion_constraints import INSERT as INSERT_INGESTION
from services.api.tests.test_ingestion_constraints import _row as _ingestion_row


def _setup_project(session_factory: SessionFactory) -> tuple[TenantContext, UUID]:
    service = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory))
    actor = ActorContext("actor:owner", f"source-asset-{uuid4().hex}")
    org = service.create_organization(actor, slug=f"org-{uuid4().hex[:8]}", name="Org")
    workspace = service.create_workspace(
        OrganizationContext(actor.actor_subject, actor.correlation_id, org.id),
        slug="main",
        name="Main",
    )
    context = TenantContext(actor.actor_subject, actor.correlation_id, org.id, workspace.id)
    project = service.create_project(context, name="Project", description=None)
    return context, project.id


def _asset_row(
    context: TenantContext,
    project_id: UUID,
    asset_id: UUID,
    version_id: UUID,
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": asset_id,
        "organization_id": context.organization_id,
        "workspace_id": context.workspace_id,
        "project_id": project_id,
        "display_name": "Source asset",
        "status": "active",
        "current_version_id": version_id,
        "latest_version_number": 1,
        "created_by_actor_subject": context.actor_subject,
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }


def _version_row(
    context: TenantContext,
    project_id: UUID,
    asset_id: UUID,
    version_id: UUID,
    *,
    version_number: int = 1,
    supersedes_version_id: UUID | None = None,
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": version_id,
        "organization_id": context.organization_id,
        "workspace_id": context.workspace_id,
        "project_id": project_id,
        "source_asset_id": asset_id,
        "version_number": version_number,
        "original_filename": "brief.pdf",
        "media_type": "application/pdf",
        "byte_size": 1024,
        "checksum_algorithm": "sha256",
        "checksum_value": "a" * 64,
        "source_type": "api_declared",
        "source_reference": "https://example.invalid/reference",
        "external_record_id": "external-1",
        "declared_created_at": None,
        "created_by_actor_subject": context.actor_subject,
        "created_at": now,
        "supersedes_version_id": supersedes_version_id,
        "metadata_schema_version": "1.0.0",
    }


INSERT_ASSET = text(
    "INSERT INTO source_assets (id, organization_id, workspace_id, project_id, display_name, "
    "status, current_version_id, latest_version_number, created_by_actor_subject, created_at, "
    "updated_at, version) VALUES (:id, :organization_id, :workspace_id, :project_id, "
    ":display_name, :status, :current_version_id, :latest_version_number, "
    ":created_by_actor_subject, :created_at, :updated_at, :version)"
)

INSERT_VERSION = text(
    "INSERT INTO source_asset_versions (id, organization_id, workspace_id, project_id, "
    "source_asset_id, version_number, original_filename, media_type, byte_size, "
    "checksum_algorithm, checksum_value, source_type, source_reference, external_record_id, "
    "declared_created_at, created_by_actor_subject, created_at, supersedes_version_id, "
    "metadata_schema_version) VALUES (:id, :organization_id, :workspace_id, :project_id, "
    ":source_asset_id, :version_number, :original_filename, :media_type, :byte_size, "
    ":checksum_algorithm, :checksum_value, :source_type, :source_reference, "
    ":external_record_id, :declared_created_at, :created_by_actor_subject, :created_at, "
    ":supersedes_version_id, :metadata_schema_version)"
)

INSERT_OPERATION = text(
    "INSERT INTO source_asset_operations (id, organization_id, workspace_id, project_id, "
    "source_asset_id, source_asset_version_id, operation, idempotency_key, request_digest, "
    "status, submitted_by_actor_subject, submitted_at, completed_at, correlation_id, version) "
    "VALUES (:id, :organization_id, :workspace_id, :project_id, :source_asset_id, "
    ":source_asset_version_id, :operation, :idempotency_key, :request_digest, :status, "
    ":submitted_by_actor_subject, :submitted_at, :completed_at, :correlation_id, :version)"
)

INSERT_ATTACHMENT = text(
    "INSERT INTO brief_ingestion_source_assets (id, organization_id, workspace_id, project_id, "
    "brief_ingestion_id, source_asset_id, source_asset_version_id, relation_type, position, "
    "attached_by_actor_subject, attached_at) VALUES (:id, :organization_id, :workspace_id, "
    ":project_id, :brief_ingestion_id, :source_asset_id, :source_asset_version_id, "
    ":relation_type, :position, :attached_by_actor_subject, :attached_at)"
)


def _insert_valid_asset(
    engine: Engine, context: TenantContext, project_id: UUID
) -> tuple[UUID, UUID]:
    asset_id, version_id = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(INSERT_ASSET, _asset_row(context, project_id, asset_id, version_id))
        connection.execute(INSERT_VERSION, _version_row(context, project_id, asset_id, version_id))
    return asset_id, version_id


def _operation_row(
    context: TenantContext,
    project_id: UUID,
    asset_id: UUID | None,
    version_id: UUID | None,
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "organization_id": context.organization_id,
        "workspace_id": context.workspace_id,
        "project_id": project_id,
        "source_asset_id": asset_id,
        "source_asset_version_id": version_id,
        "operation": "create_source_asset",
        "idempotency_key": f"operation-{uuid4().hex}",
        "request_digest": "a" * 64,
        "status": "accepted",
        "submitted_by_actor_subject": context.actor_subject,
        "submitted_at": now,
        "completed_at": now,
        "correlation_id": "source-operation-constraint",
        "version": 1,
    }


def _attachment_row(
    context: TenantContext,
    project_id: UUID,
    ingestion_id: UUID,
    asset_id: UUID,
    version_id: UUID,
) -> dict[str, object]:
    return {
        "id": uuid4(),
        "organization_id": context.organization_id,
        "workspace_id": context.workspace_id,
        "project_id": project_id,
        "brief_ingestion_id": ingestion_id,
        "source_asset_id": asset_id,
        "source_asset_version_id": version_id,
        "relation_type": "primary_source",
        "position": 0,
        "attached_by_actor_subject": context.actor_subject,
        "attached_at": datetime.now(UTC),
    }


def _insert_accepted_ingestion(
    engine: Engine, session_factory: SessionFactory
) -> tuple[TenantContext, UUID, UUID]:
    context, project_id, brief_id, version_id = _setup_brief(session_factory)
    row = _ingestion_row(
        context.organization_id, context.workspace_id, project_id, brief_id, version_id
    )
    with engine.begin() as connection:
        connection.execute(INSERT_INGESTION, row)
    return context, project_id, row["id"]  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("asset", "status", "deleted"),
        ("asset", "latest_version_number", 0),
        ("asset", "version", 0),
        ("version", "version_number", 0),
        ("version", "byte_size", 0),
        ("version", "byte_size", 104857601),
        ("version", "checksum_algorithm", "md5"),
        ("version", "checksum_value", "A" * 64),
        ("version", "checksum_value", "g" * 64),
        ("version", "media_type", "image/png"),
        ("version", "source_type", "uploaded_bytes"),
        ("version", "metadata_schema_version", "2.0.0"),
    ],
)
def test_source_asset_database_checks_reject_invalid_rows(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    target: str,
    field: str,
    value: object,
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_id, version_id = uuid4(), uuid4()
    asset_row = _asset_row(context, project_id, asset_id, version_id)
    version_row = _version_row(context, project_id, asset_id, version_id)
    (asset_row if target == "asset" else version_row)[field] = value

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ASSET, asset_row)
        connection.execute(INSERT_VERSION, version_row)


def test_source_asset_project_tenant_mismatch_is_rejected(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context_a, _ = _setup_project(persistence_session_factory)
    _, project_b = _setup_project(persistence_session_factory)
    asset_id, version_id = uuid4(), uuid4()

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ASSET, _asset_row(context_a, project_b, asset_id, version_id))
        connection.execute(INSERT_VERSION, _version_row(context_a, project_b, asset_id, version_id))


def test_source_asset_version_tenant_mismatch_is_rejected(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context_a, project_a = _setup_project(persistence_session_factory)
    context_b, project_b = _setup_project(persistence_session_factory)
    asset_id, version_id = _insert_valid_asset(database_engine, context_a, project_a)

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(
            INSERT_VERSION,
            _version_row(context_b, project_b, asset_id, uuid4(), version_number=2),
        )

    assert version_id is not None


def test_source_asset_current_pointer_must_target_same_asset(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_a, version_a = uuid4(), uuid4()
    asset_b, version_b = uuid4(), uuid4()

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ASSET, _asset_row(context, project_id, asset_a, version_b))
        connection.execute(INSERT_ASSET, _asset_row(context, project_id, asset_b, version_b))
        connection.execute(INSERT_VERSION, _version_row(context, project_id, asset_a, version_a))
        connection.execute(INSERT_VERSION, _version_row(context, project_id, asset_b, version_b))


def test_source_asset_supersedes_must_target_same_asset(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_a, version_a = _insert_valid_asset(database_engine, context, project_id)
    asset_b, version_b = _insert_valid_asset(database_engine, context, project_id)
    del version_b

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(
            INSERT_VERSION,
            _version_row(
                context,
                project_id,
                asset_b,
                uuid4(),
                version_number=2,
                supersedes_version_id=version_a,
            ),
        )

    assert asset_a is not None


def test_source_asset_duplicate_version_number_is_rejected(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_id, version_id = _insert_valid_asset(database_engine, context, project_id)

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(
            INSERT_VERSION,
            _version_row(context, project_id, asset_id, uuid4(), supersedes_version_id=version_id),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "reserved", "source_asset_id": "keep"},
        {"status": "reserved", "source_asset_version_id": "keep"},
        {"status": "reserved", "completed_at": "keep"},
        {"status": "accepted", "source_asset_id": None},
        {"status": "accepted", "source_asset_version_id": None},
        {"status": "accepted", "completed_at": None},
        {"operation": "unsupported"},
        {"status": "rejected"},
        {"request_digest": "not-a-digest"},
        {"version": 0},
    ],
)
def test_source_asset_operation_database_checks_reject_invalid_rows(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    overrides: dict[str, object],
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_id, version_id = _insert_valid_asset(database_engine, context, project_id)
    row = _operation_row(context, project_id, asset_id, version_id)
    for field, value in overrides.items():
        row[field] = row[field] if value == "keep" else value
    if row["status"] == "reserved":
        row["source_asset_id"] = (
            None if "source_asset_id" not in overrides else row["source_asset_id"]
        )
        row["source_asset_version_id"] = (
            None if "source_asset_version_id" not in overrides else row["source_asset_version_id"]
        )
        row["completed_at"] = None if "completed_at" not in overrides else row["completed_at"]

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, row)


def test_source_asset_operation_scoped_unique_constraint(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_id, version_id = _insert_valid_asset(database_engine, context, project_id)
    row = _operation_row(context, project_id, asset_id, version_id)
    row["idempotency_key"] = "same-key"
    with database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, row)

    duplicate = dict(row, id=uuid4())
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, duplicate)

    other_operation = dict(row, id=uuid4(), operation="archive_source_asset")
    with database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, other_operation)


@pytest.mark.parametrize("operation", ["create_source_asset", "archive_source_asset"])
def test_source_asset_operation_requires_a_version_for_every_accepted_outcome(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    operation: str,
) -> None:
    del clean_database
    context, project_id = _setup_project(persistence_session_factory)
    asset_id, version_id = _insert_valid_asset(database_engine, context, project_id)
    row = _operation_row(context, project_id, asset_id, version_id)
    row.update(operation=operation, source_asset_version_id=None)

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, row)


def test_source_asset_operation_composite_foreign_keys_reject_mismatched_outcomes(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context_a, project_a = _setup_project(persistence_session_factory)
    context_b, project_b = _setup_project(persistence_session_factory)
    asset_a, version_a = _insert_valid_asset(database_engine, context_a, project_a)
    asset_b, version_b = _insert_valid_asset(database_engine, context_b, project_b)

    cross_tenant = _operation_row(context_a, project_a, asset_b, version_b)
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, cross_tenant)

    _, version_c = _insert_valid_asset(database_engine, context_a, project_a)
    mismatched_asset_version = _operation_row(context_a, project_a, asset_a, version_c)
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_OPERATION, mismatched_asset_version)

    assert version_a is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"relation_type": "invalid"},
        {"position": -1},
    ],
)
def test_brief_ingestion_source_attachment_checks_reject_invalid_rows(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    overrides: dict[str, object],
) -> None:
    del clean_database
    context, project_id, ingestion_id = _insert_accepted_ingestion(
        database_engine, persistence_session_factory
    )
    asset_id, version_id = _insert_valid_asset(database_engine, context, project_id)
    row = _attachment_row(context, project_id, ingestion_id, asset_id, version_id)
    row.update(overrides)

    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, row)


def test_brief_ingestion_source_attachment_foreign_keys_and_unique_constraints(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context_a, project_a, ingestion_a = _insert_accepted_ingestion(
        database_engine, persistence_session_factory
    )
    context_b, project_b, ingestion_b = _insert_accepted_ingestion(
        database_engine, persistence_session_factory
    )
    asset_a, version_a = _insert_valid_asset(database_engine, context_a, project_a)
    asset_b, version_b = _insert_valid_asset(database_engine, context_b, project_b)

    valid = _attachment_row(context_a, project_a, ingestion_a, asset_a, version_a)
    with database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, valid)

    duplicate = dict(valid, id=uuid4())
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, duplicate)

    wrong_project_ingestion = _attachment_row(context_a, project_a, ingestion_b, asset_a, version_a)
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, wrong_project_ingestion)

    cross_tenant_asset = _attachment_row(context_a, project_a, ingestion_a, asset_b, version_b)
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, cross_tenant_asset)

    other_project = TenantApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).create_project(context_a, name="Other Project", description=None)
    other_project_asset, other_project_version = _insert_valid_asset(
        database_engine, context_a, other_project.id
    )
    wrong_project_asset = _attachment_row(
        context_a, project_a, ingestion_a, other_project_asset, other_project_version
    )
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, wrong_project_asset)

    mismatched_version = _attachment_row(context_a, project_a, ingestion_a, asset_a, version_b)
    mismatched_version["position"] = 1
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, mismatched_version)

    position_collision = _attachment_row(context_a, project_a, ingestion_a, asset_a, version_a)
    position_collision.update(id=uuid4(), relation_type="reference")
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, position_collision)

    missing_ingestion = _attachment_row(context_a, project_a, uuid4(), asset_a, version_a)
    missing_ingestion["position"] = 1
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, missing_ingestion)

    missing_version = _attachment_row(context_a, project_a, ingestion_a, asset_a, uuid4())
    missing_version["position"] = 1
    with pytest.raises(IntegrityError), database_engine.begin() as connection:
        connection.execute(INSERT_ATTACHMENT, missing_version)


def test_attachment_repository_requires_an_accepted_ingestion(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    context, project_id, brief_id, version_id = _setup_brief(persistence_session_factory)
    reserved = _ingestion_row(
        context.organization_id, context.workspace_id, project_id, brief_id, version_id
    )
    reserved.update(
        brief_id=None,
        brief_version_id=None,
        status="reserved",
        completed_at=None,
    )
    with database_engine.begin() as connection:
        connection.execute(INSERT_INGESTION, reserved)
    asset_id, asset_version_id = _insert_valid_asset(database_engine, context, project_id)

    with persistence_session_factory() as session:
        repository = SqlAlchemyBriefIngestionSourceAssetRepository(session)
        attachment = BriefIngestionSourceAsset(
            id=uuid4(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            brief_ingestion_id=reserved["id"],  # type: ignore[arg-type]
            source_asset_id=asset_id,
            source_asset_version_id=asset_version_id,
            relation_type=BriefIngestionSourceAssetRelationType.PRIMARY_SOURCE,
            position=0,
            attached_by_actor_subject=context.actor_subject,
            attached_at=datetime.now(UTC),
        )
        with pytest.raises(ResourceConflict, match="accepted ingestion"):
            repository.add_for_accepted_ingestion(attachment)
        assert session.scalar(text("SELECT count(*) FROM brief_ingestion_source_assets")) == 0
        session.rollback()
