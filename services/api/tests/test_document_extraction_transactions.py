import asyncio
import hashlib
import os
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.context import TenantContext
from services.api.app.application.document_extraction_services import (
    DocumentExtractionApplicationService,
)
from services.api.app.application.errors import ResourceConflict, StorageUnavailable
from services.api.app.application.source_asset_services import SourceAssetApplicationService
from services.api.app.application.source_object_services import SourceObjectApplicationService
from services.api.app.application.storage import LocalFilesystemStorageAdapter
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_source_asset_services import _bootstrap, _create
from services.api.tests.test_source_object_transactions import _FailingAuditUoW, _FailureState


async def _chunks(content: bytes) -> AsyncIterator[bytes]:
    yield content[: max(1, len(content) // 2)]
    yield content[max(1, len(content) // 2) :]


def _prepared(
    session_factory: SessionFactory, storage: LocalFilesystemStorageAdapter, content: bytes
) -> tuple[TenantContext, UUID, UUID, UUID]:
    context, project_id = _bootstrap(session_factory)
    metadata = _create(
        SourceAssetApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory)),
        context,
        project_id,
        byte_size=len(content),
        checksum_value=hashlib.sha256(content).hexdigest(),
        media_type="text/plain",
    )
    uploader = SourceObjectApplicationService(
        lambda: SqlAlchemyUnitOfWork(session_factory),
        storage,
        max_upload_bytes=max(1024, len(content)),
    )
    asyncio.run(
        uploader.upload(
            context,
            project_id,
            metadata.asset.id,
            metadata.version.id,
            idempotency_key="prepare-extraction-upload",
            chunks=_chunks(content),
        )
    )
    return context, project_id, metadata.asset.id, metadata.version.id


def test_audit_failure_rolls_back_extraction_and_operation(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    storage = LocalFilesystemStorageAdapter(tmp_path)
    target = _prepared(persistence_session_factory, storage, b"rollback extraction")
    state = _FailureState(1)
    service = DocumentExtractionApplicationService(
        lambda: _FailingAuditUoW(persistence_session_factory, state), storage
    )
    with pytest.raises(RuntimeError, match="audit failure"):
        service.create(*target, idempotency_key="failed-extraction-key")
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_extractions")) == 0
        assert connection.scalar(text("SELECT count(*) FROM document_extraction_operations")) == 0


def test_tampered_object_is_rejected_before_extraction_commit(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    storage = LocalFilesystemStorageAdapter(tmp_path)
    target = _prepared(persistence_session_factory, storage, b"original")
    with database_engine.connect() as connection:
        key = str(connection.scalar(text("SELECT storage_key FROM source_objects")))
    path = storage.object_root / key
    os.chmod(path, 0o600)
    path.write_bytes(b"tampered")
    service = DocumentExtractionApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory), storage
    )
    with pytest.raises(StorageUnavailable, match="integrity"):
        service.create(*target, idempotency_key="tampered-extraction-key")
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_extractions")) == 0


def test_concurrent_replay_and_unique_parser_result(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    storage = LocalFilesystemStorageAdapter(tmp_path)
    target = _prepared(persistence_session_factory, storage, b"concurrent extraction")
    service = DocumentExtractionApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory), storage
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(service.create, *target, idempotency_key="concurrent-extraction-key")
            for _ in range(2)
        ]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result.replayed for result in results) == [False, True]
    assert len({result.extraction.id for result in results}) == 1
    with pytest.raises(ResourceConflict):
        service.create(*target, idempotency_key="different-key-same-parser")
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM document_extractions), "
                "(SELECT count(*) FROM document_extraction_operations), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='document_extraction.completed')"
            )
        ).one()
    assert counts == (1, 1, 1)
