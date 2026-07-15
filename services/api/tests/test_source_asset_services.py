from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.context import ActorContext, OrganizationContext, TenantContext
from services.api.app.application.errors import ResourceConflict, ResourceNotFound
from services.api.app.application.repositories import (
    AuditEventRepository,
    SourceAssetOperationRepository,
)
from services.api.app.application.services import TenantApplicationService
from services.api.app.application.source_asset_services import (
    SourceAssetApplicationService,
    SourceAssetResult,
)
from services.api.app.domain import (
    AuditEvent,
    MembershipRole,
    SourceAssetOperation,
    SourceAssetOperationStatus,
    SourceAssetOperationType,
    SourceAssetStatus,
    VersionConflict,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.repositories import SqlAlchemySourceAssetOperationRepository
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork


def _actor(subject: str = "actor:owner") -> ActorContext:
    return ActorContext(subject, f"source-asset-{uuid4().hex}")


def _bootstrap(
    session_factory: SessionFactory, *, role: MembershipRole | None = None
) -> tuple[TenantContext, UUID]:
    service = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory))
    owner = _actor()
    org = service.create_organization(owner, slug=f"org-{uuid4().hex[:8]}", name="Org")
    workspace = service.create_workspace(
        OrganizationContext(owner.actor_subject, owner.correlation_id, org.id),
        slug="main",
        name="Main",
    )
    context = TenantContext(owner.actor_subject, owner.correlation_id, org.id, workspace.id)
    if role is not None:
        subject = f"actor:{role.value}-{uuid4().hex[:8]}"
        service.create_membership(context, actor_subject=subject, role=role)
        context = TenantContext(subject, f"source-asset-{uuid4().hex}", org.id, workspace.id)
    project = service.create_project(
        context if role is None else _owner_context(org.id, workspace.id),
        name="Project",
        description=None,
    )
    return context, project.id


def _owner_context(organization_id: UUID, workspace_id: UUID) -> TenantContext:
    return TenantContext(
        "actor:owner", f"source-asset-{uuid4().hex}", organization_id, workspace_id
    )


def _metadata(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "display_name": "Source Asset",
        "original_filename": "source.pdf",
        "media_type": "application/pdf",
        "byte_size": 1024,
        "checksum_algorithm": "sha256",
        "checksum_value": "a" * 64,
        "source_type": "api_declared",
        "source_reference": "https://example.invalid/source",
        "external_record_id": "external-1",
        "declared_created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return values


def _service(session_factory: SessionFactory) -> SourceAssetApplicationService:
    return SourceAssetApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory))


def _create(
    service: SourceAssetApplicationService,
    context: TenantContext,
    project_id: UUID,
    *,
    key: str = "create-key",
    **overrides: object,
) -> SourceAssetResult:
    values = _metadata(**overrides)
    return service.create_asset(
        context,
        project_id,
        idempotency_key=key,
        display_name=cast(str, values["display_name"]),
        original_filename=cast(str, values["original_filename"]),
        media_type=cast(str, values["media_type"]),
        byte_size=cast(int, values["byte_size"]),
        checksum_algorithm=cast(str, values["checksum_algorithm"]),
        checksum_value=cast(str, values["checksum_value"]),
        source_type=cast(str, values["source_type"]),
        source_reference=cast(str | None, values["source_reference"]),
        external_record_id=cast(str | None, values["external_record_id"]),
        declared_created_at=cast(datetime | None, values["declared_created_at"]),
    )


def test_source_asset_repository_scope_and_version_lookup(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    context_a, project_a = _bootstrap(persistence_session_factory)
    context_b, project_b = _bootstrap(persistence_session_factory)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    result = _create(service, context_a, project_a)

    with SqlAlchemyUnitOfWork(persistence_session_factory) as uow:
        assert (
            uow.source_assets.get(
                context_a.organization_id, context_a.workspace_id, project_a, result.asset.id
            )
            == result.asset
        )
        assert (
            uow.source_assets.get(
                context_b.organization_id, context_b.workspace_id, project_b, result.asset.id
            )
            is None
        )
        assert (
            uow.source_asset_versions.get(
                context_a.organization_id,
                context_a.workspace_id,
                project_a,
                uuid4(),
                result.version.id,
            )
            is None
        )
        assert (
            uow.source_asset_versions.find_declared_duplicate_within_project(
                context_a.organization_id,
                context_a.workspace_id,
                project_a,
                checksum_algorithm="sha256",
                checksum_value="a" * 64,
                byte_size=1024,
                media_type="application/pdf",
            )
            == 1
        )


def test_source_asset_create_version_cas_and_predecessor_immutability(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    created = _create(service, context, project_id)
    predecessor = created.version

    updated = service.create_version(
        context,
        project_id,
        created.asset.id,
        idempotency_key="version-key",
        expected_asset_version=created.asset.version,
        expected_current_version_id=created.asset.current_version_id,
        source_version_id=created.version.id,
        original_filename="source-v2.pdf",
        media_type="application/pdf",
        byte_size=2048,
        checksum_algorithm="sha256",
        checksum_value="b" * 64,
        source_type="api_declared",
        source_reference=None,
        external_record_id=None,
        declared_created_at=None,
    )

    with SqlAlchemyUnitOfWork(persistence_session_factory) as uow:
        loaded_predecessor = uow.source_asset_versions.get(
            context.organization_id,
            context.workspace_id,
            project_id,
            created.asset.id,
            predecessor.id,
        )
    assert loaded_predecessor == predecessor
    assert updated.asset.current_version_id == updated.version.id
    assert updated.asset.latest_version_number == 2
    assert updated.asset.version == 2
    assert updated.version.supersedes_version_id == predecessor.id


def test_source_asset_cas_rejects_stale_pointer_and_rolls_back(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    created = _create(service, context, project_id)

    with pytest.raises(VersionConflict):
        service.create_version(
            context,
            project_id,
            created.asset.id,
            idempotency_key="stale-pointer",
            expected_asset_version=created.asset.version,
            expected_current_version_id=uuid4(),
            source_version_id=created.version.id,
            original_filename="source-v2.pdf",
            media_type="application/pdf",
            byte_size=2048,
            checksum_algorithm="sha256",
            checksum_value="b" * 64,
            source_type="api_declared",
            source_reference=None,
            external_record_id=None,
            declared_created_at=None,
        )

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_asset_versions), "
                "(SELECT count(*) FROM source_asset_operations WHERE status = 'accepted'), "
                "(SELECT count(*) FROM source_asset_operations WHERE status = 'reserved')"
            )
        ).one()
    assert tuple(counts) == (1, 1, 0)


def test_source_asset_archive_cas_and_role(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    created = _create(service, context, project_id)
    archived = service.archive_asset(
        context,
        project_id,
        created.asset.id,
        idempotency_key="archive-key",
        expected_asset_version=created.asset.version,
        expected_current_version_id=created.asset.current_version_id,
    )
    assert archived.asset.status is SourceAssetStatus.ARCHIVED
    assert archived.asset.version == 2

    with pytest.raises(VersionConflict):
        service.archive_asset(
            context,
            project_id,
            created.asset.id,
            idempotency_key="archive-stale",
            expected_asset_version=created.asset.version,
            expected_current_version_id=created.asset.current_version_id,
        )


def test_source_asset_idempotency_replay_conflict_and_later_aggregate_change(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    created = _create(service, context, project_id, key="same-key")
    service.create_version(
        context,
        project_id,
        created.asset.id,
        idempotency_key="advance-key",
        expected_asset_version=created.asset.version,
        expected_current_version_id=created.asset.current_version_id,
        source_version_id=created.version.id,
        original_filename="source-v2.pdf",
        media_type="application/pdf",
        byte_size=2048,
        checksum_algorithm="sha256",
        checksum_value="b" * 64,
        source_type="api_declared",
        source_reference=None,
        external_record_id=None,
        declared_created_at=None,
    )

    replay = _create(service, context, project_id, key="same-key")
    with pytest.raises(ResourceConflict) as conflict:
        _create(service, context, project_id, key="same-key", byte_size=2048)

    with database_engine.connect() as connection:
        audit_count = connection.scalar(
            text(
                "SELECT count(*) FROM audit_events "
                "WHERE action = 'source_asset.created' AND aggregate_id = :asset_id"
            ),
            {"asset_id": created.asset.id},
        )
        reserved_count = connection.scalar(
            text("SELECT count(*) FROM source_asset_operations WHERE status = 'reserved'")
        )
    assert replay.replayed is True
    assert replay.asset.id == created.asset.id
    assert replay.version.id == created.version.id
    assert conflict.value.code == "idempotency_conflict"
    assert audit_count == 1
    assert reserved_count == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_reference": "external-record:changed"},
        {"declared_created_at": datetime(2026, 1, 2, tzinfo=UTC)},
    ],
)
def test_source_asset_create_digest_covers_all_provenance_metadata(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    overrides: dict[str, object],
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = _service(persistence_session_factory)
    _create(service, context, project_id, key="metadata-digest-key")

    with pytest.raises(ResourceConflict) as conflict:
        _create(service, context, project_id, key="metadata-digest-key", **overrides)

    assert conflict.value.code == "idempotency_conflict"


def test_source_asset_version_digest_covers_expected_pointer(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = _service(persistence_session_factory)
    created = _create(service, context, project_id)
    service.create_version(
        context,
        project_id,
        created.asset.id,
        idempotency_key="version-digest-key",
        expected_asset_version=created.asset.version,
        expected_current_version_id=created.asset.current_version_id,
        source_version_id=created.version.id,
        original_filename="source-v2.pdf",
        media_type="application/pdf",
        byte_size=2048,
        checksum_algorithm="sha256",
        checksum_value="b" * 64,
        source_type="api_declared",
        source_reference=None,
        external_record_id=None,
        declared_created_at=None,
    )

    with pytest.raises(ResourceConflict) as conflict:
        service.create_version(
            context,
            project_id,
            created.asset.id,
            idempotency_key="version-digest-key",
            expected_asset_version=created.asset.version,
            expected_current_version_id=uuid4(),
            source_version_id=created.version.id,
            original_filename="source-v2.pdf",
            media_type="application/pdf",
            byte_size=2048,
            checksum_algorithm="sha256",
            checksum_value="b" * 64,
            source_type="api_declared",
            source_reference=None,
            external_record_id=None,
            declared_created_at=None,
        )

    assert conflict.value.code == "idempotency_conflict"


def test_concurrent_source_asset_create_replays_without_duplicate_mutation(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    start = Barrier(2)

    def create() -> SourceAssetResult:
        assert start.wait(timeout=5) in (0, 1)
        return _create(_service(persistence_session_factory), context, project_id, key="concurrent")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_assets), "
                "(SELECT count(*) FROM source_asset_versions), "
                "(SELECT count(*) FROM source_asset_operations WHERE status = 'accepted'), "
                "(SELECT count(*) FROM source_asset_operations WHERE status = 'reserved'), "
                "(SELECT count(*) FROM audit_events WHERE action = 'source_asset.created')"
            )
        ).one()
    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].asset.id == results[1].asset.id
    assert tuple(counts) == (1, 1, 1, 0, 1)


def test_concurrent_source_asset_version_create_has_one_successor(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    service = _service(persistence_session_factory)
    created = _create(service, context, project_id)
    start = Barrier(2)

    def create_version() -> SourceAssetResult:
        assert start.wait(timeout=5) in (0, 1)
        return _service(persistence_session_factory).create_version(
            context,
            project_id,
            created.asset.id,
            idempotency_key="concurrent-version",
            expected_asset_version=created.asset.version,
            expected_current_version_id=created.asset.current_version_id,
            source_version_id=created.version.id,
            original_filename="source-v2.pdf",
            media_type="application/pdf",
            byte_size=2048,
            checksum_algorithm="sha256",
            checksum_value="b" * 64,
            source_type="api_declared",
            source_reference=None,
            external_record_id=None,
            declared_created_at=None,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create_version) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_asset_versions), "
                "(SELECT count(*) FROM source_asset_operations WHERE status = 'accepted'), "
                "(SELECT count(*) FROM source_asset_operations WHERE status = 'reserved'), "
                "(SELECT count(*) FROM audit_events WHERE action = 'source_asset.version_created')"
            )
        ).one()
    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].version.id == results[1].version.id
    assert tuple(counts) == (2, 2, 0, 1)


def test_source_asset_reservation_rolls_back_and_allows_a_new_winner(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    winner_reserved, loser_started = Event(), Event()

    def reservation() -> SourceAssetOperation:
        now = datetime.now(UTC)
        return SourceAssetOperation(
            id=uuid4(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            source_asset_id=None,
            source_asset_version_id=None,
            operation=SourceAssetOperationType.CREATE_SOURCE_ASSET,
            idempotency_key="rollback-takeover",
            request_digest="a" * 64,
            status=SourceAssetOperationStatus.RESERVED,
            submitted_by_actor_subject=context.actor_subject,
            submitted_at=now,
            completed_at=None,
            correlation_id=context.correlation_id,
            version=1,
        )

    def winner() -> None:
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            assert (
                SqlAlchemySourceAssetOperationRepository(session).reserve(reservation()) is not None
            )
            winner_reserved.set()
            assert loser_started.wait(5)
            session.rollback()

    def loser() -> SourceAssetOperation | None:
        assert winner_reserved.wait(5)
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            loser_started.set()
            won = SqlAlchemySourceAssetOperationRepository(session).reserve(reservation())
            session.rollback()
            return won

    with ThreadPoolExecutor(max_workers=2) as executor:
        winner_future = executor.submit(winner)
        loser_future = executor.submit(loser)
        winner_future.result(timeout=10)
        assert loser_future.result(timeout=10) is not None

    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM source_asset_operations")) == 0


def test_source_asset_idempotency_scope_is_project_and_operation_specific(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    context, project_a = _bootstrap(persistence_session_factory)
    tenant = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    project_b = tenant.create_project(context, name="Project B", description=None)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )

    first = _create(service, context, project_a, key="scoped-key")
    second = _create(service, context, project_b.id, key="scoped-key", checksum_value="b" * 64)
    archived = service.archive_asset(
        context,
        project_a,
        first.asset.id,
        idempotency_key="scoped-key",
        expected_asset_version=first.asset.version,
        expected_current_version_id=first.asset.current_version_id,
    )

    assert first.asset.id != second.asset.id
    assert archived.operation.operation is SourceAssetOperationType.ARCHIVE_SOURCE_ASSET


class FailingAuditRepository(AuditEventRepository):
    def append(self, event: AuditEvent) -> AuditEvent:
        del event
        raise RuntimeError("audit failure")

    def list_for_project(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[AuditEvent]:
        del organization_id, workspace_id, project_id
        return []

    def list_for_brief(
        self, organization_id: UUID, workspace_id: UUID, brief_id: UUID
    ) -> list[AuditEvent]:
        del organization_id, workspace_id, brief_id
        return []


class FailingFinalizeRepository(SourceAssetOperationRepository):
    def __init__(self) -> None:
        self.operation: SourceAssetOperation | None = None

    def reserve(self, operation: SourceAssetOperation) -> SourceAssetOperation | None:
        self.operation = operation
        return operation

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: SourceAssetOperationType,
        idempotency_key: str,
    ) -> SourceAssetOperation | None:
        del organization_id, workspace_id, project_id, operation, idempotency_key
        return self.operation

    def finalize_accepted(
        self,
        operation: SourceAssetOperation,
        *,
        source_asset_id: UUID,
        source_asset_version_id: UUID | None,
        completed_at: datetime,
        expected_version: int,
    ) -> SourceAssetOperation:
        del operation, source_asset_id, source_asset_version_id, completed_at, expected_version
        raise RuntimeError("finalize failure")


class FailingAuditUnitOfWork(SqlAlchemyUnitOfWork):
    def __enter__(self) -> "FailingAuditUnitOfWork":
        super().__enter__()
        self.audit_events = FailingAuditRepository()
        return self


class FailingFinalizeUnitOfWork(SqlAlchemyUnitOfWork):
    def __enter__(self) -> "FailingFinalizeUnitOfWork":
        super().__enter__()
        self.source_asset_operations = FailingFinalizeRepository()
        return self


def test_source_asset_audit_failure_rolls_back_everything(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    failing = SourceAssetApplicationService(
        lambda: FailingAuditUnitOfWork(persistence_session_factory)
    )

    with pytest.raises(RuntimeError, match="audit failure"):
        _create(failing, context, project_id)

    _assert_source_counts(database_engine, assets=0, versions=0, operations=0, audits=0)


def test_source_asset_finalize_failure_rolls_back_everything(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id = _bootstrap(persistence_session_factory)
    failing = SourceAssetApplicationService(
        lambda: FailingFinalizeUnitOfWork(persistence_session_factory)
    )

    with pytest.raises(RuntimeError, match="finalize failure"):
        _create(failing, context, project_id)

    _assert_source_counts(database_engine, assets=0, versions=0, operations=0, audits=0)


def test_source_asset_viewer_is_read_only(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    owner_context, project_id = _bootstrap(persistence_session_factory)
    service = SourceAssetApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    created = _create(service, owner_context, project_id)
    viewer_context, _ = _bootstrap(persistence_session_factory, role=MembershipRole.VIEWER)

    assert service.get_asset(owner_context, project_id, created.asset.id) == created.asset
    with pytest.raises(ResourceNotFound):
        _create(service, viewer_context, project_id)


def _assert_source_counts(
    engine: Engine, *, assets: int, versions: int, operations: int, audits: int
) -> None:
    with engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_assets), "
                "(SELECT count(*) FROM source_asset_versions), "
                "(SELECT count(*) FROM source_asset_operations), "
                "(SELECT count(*) FROM audit_events WHERE action LIKE 'source_asset.%')"
            )
        ).one()
    assert tuple(counts) == (assets, versions, operations, audits)
