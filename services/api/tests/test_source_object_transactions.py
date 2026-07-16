import asyncio
import hashlib
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import StorageUnavailable
from services.api.app.application.repositories import AuditEventRepository
from services.api.app.application.source_asset_services import SourceAssetApplicationService
from services.api.app.application.source_object_services import (
    SourceObjectApplicationService,
    SourceObjectUploadResult,
)
from services.api.app.application.storage import LocalFilesystemStorageAdapter, StorageError
from services.api.app.domain import AuditEvent
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_source_asset_services import _bootstrap, _create


async def _chunks(content: bytes, barrier: Barrier | None = None) -> AsyncIterator[bytes]:
    if barrier is not None:
        barrier.wait(timeout=10)
    midpoint = max(1, len(content) // 2)
    yield content[:midpoint]
    yield content[midpoint:]


class _FailingAuditRepository:
    def __init__(self, delegate: AuditEventRepository, state: "_FailureState") -> None:
        self.delegate = delegate
        self.state = state

    def append(self, event: AuditEvent) -> AuditEvent:
        with self.state.lock:
            if self.state.remaining > 0:
                self.state.remaining -= 1
                raise RuntimeError("simulated audit failure")
        return self.delegate.append(event)

    def list_for_project(self, *args: Any, **kwargs: Any) -> list[AuditEvent]:
        return self.delegate.list_for_project(*args, **kwargs)

    def list_for_brief(self, *args: Any, **kwargs: Any) -> list[AuditEvent]:
        return self.delegate.list_for_brief(*args, **kwargs)


class _FailureState:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining
        self.lock = Lock()


class _FailingAuditUoW(SqlAlchemyUnitOfWork):
    def __init__(self, session_factory: SessionFactory, state: _FailureState) -> None:
        super().__init__(session_factory)
        self.state = state

    def __enter__(self) -> "_FailingAuditUoW":
        super().__enter__()
        self.audit_events = _FailingAuditRepository(self.audit_events, self.state)
        return self


class _DeleteFailingStorage(LocalFilesystemStorageAdapter):
    def delete(self, storage_key: str) -> None:
        if storage_key.startswith("object-"):
            raise StorageError("simulated cleanup failure")
        super().delete(storage_key)


class _FinalizeFailingStorage(LocalFilesystemStorageAdapter):
    def finalize(self, staging_key: str, final_key: str) -> None:
        del staging_key, final_key
        raise StorageError("simulated finalize failure")


def _target(
    session_factory: SessionFactory, content: bytes
) -> tuple[TenantContext, UUID, UUID, UUID]:
    context, project_id = _bootstrap(session_factory)
    created = _create(
        SourceAssetApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory)),
        context,
        project_id,
        byte_size=len(content),
        checksum_value=hashlib.sha256(content).hexdigest(),
        media_type="text/plain",
    )
    return context, project_id, created.asset.id, created.version.id


def _upload(
    service: SourceObjectApplicationService,
    target: tuple[TenantContext, UUID, UUID, UUID],
    content: bytes,
    key: str,
    barrier: Barrier | None = None,
) -> SourceObjectUploadResult:
    context, project_id, asset_id, version_id = target
    return asyncio.run(
        service.upload(
            context,
            project_id,
            asset_id,
            version_id,
            idempotency_key=key,
            chunks=_chunks(content, barrier),
        )
    )


def test_audit_failure_rolls_back_database_and_deletes_final_object(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    content = b"atomic upload"
    target = _target(persistence_session_factory, content)
    state = _FailureState(1)
    storage = LocalFilesystemStorageAdapter(tmp_path)
    service = SourceObjectApplicationService(
        lambda: _FailingAuditUoW(persistence_session_factory, state),
        storage,
        max_upload_bytes=1024,
    )

    with pytest.raises(RuntimeError, match="audit failure"):
        _upload(service, target, content, "audit-failure-upload")

    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM source_objects")) == 0
        assert connection.scalar(text("SELECT count(*) FROM source_object_uploads")) == 0
    assert not any(storage.staging_root.iterdir())
    assert not any(storage.object_root.iterdir())


def test_cleanup_failure_records_bounded_requirement(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    content = b"cleanup record"
    target = _target(persistence_session_factory, content)
    state = _FailureState(1)
    storage = _DeleteFailingStorage(tmp_path)
    service = SourceObjectApplicationService(
        lambda: _FailingAuditUoW(persistence_session_factory, state),
        storage,
        max_upload_bytes=1024,
    )
    with pytest.raises(RuntimeError):
        _upload(service, target, content, "cleanup-failure-upload")

    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM source_objects")) == 0
        assert connection.scalar(text("SELECT count(*) FROM source_object_uploads")) == 0
        requirement = connection.execute(
            text("SELECT reason_code, storage_key FROM source_object_cleanup_requirements")
        ).one()
    assert requirement[0] == "database_failure"
    assert str(requirement[1]).startswith("object-")
    assert len(list(storage.object_root.iterdir())) == 1


def test_finalize_failure_rolls_back_reservation_and_removes_stage(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    content = b"finalize fails"
    target = _target(persistence_session_factory, content)
    storage = _FinalizeFailingStorage(tmp_path)
    service = SourceObjectApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory),
        storage,
        max_upload_bytes=1024,
    )
    with pytest.raises(StorageUnavailable, match="storage is unavailable"):
        _upload(service, target, content, "finalize-failure-upload")
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM source_object_uploads")) == 0
    assert not any(storage.staging_root.iterdir())


def test_concurrent_same_key_has_one_object_one_audit_and_replay(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    content = b"concurrent upload"
    target = _target(persistence_session_factory, content)
    storage = LocalFilesystemStorageAdapter(tmp_path)
    service = SourceObjectApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory),
        storage,
        max_upload_bytes=1024,
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_upload, service, target, content, "concurrent-upload-key", barrier)
            for _ in range(2)
        ]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result.replayed for result in results) == [False, True]
    assert len({result.source_object.id for result in results}) == 1
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_objects), "
                "(SELECT count(*) FROM source_object_uploads), "
                "(SELECT count(*) FROM audit_events WHERE action='source_object.uploaded'), "
                "(SELECT count(*) FROM source_object_uploads WHERE status='reserved')"
            )
        ).one()
    assert counts == (1, 1, 1, 0)


def test_winner_rollback_allows_loser_to_take_reservation(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    content = b"winner rollback"
    target = _target(persistence_session_factory, content)
    state = _FailureState(1)
    storage = LocalFilesystemStorageAdapter(tmp_path)
    service = SourceObjectApplicationService(
        lambda: _FailingAuditUoW(persistence_session_factory, state),
        storage,
        max_upload_bytes=1024,
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_upload, service, target, content, "rollback-takeover-key", barrier)
            for _ in range(2)
        ]
        outcomes: list[object] = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=15))
            except RuntimeError as error:
                outcomes.append(error)
    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM source_objects), "
                "(SELECT count(*) FROM source_object_uploads WHERE status='accepted'), "
                "(SELECT count(*) FROM source_object_uploads WHERE status='reserved'), "
                "(SELECT count(*) FROM audit_events WHERE action='source_object.uploaded')"
            )
        ).one()
    assert counts == (1, 1, 0, 1)
