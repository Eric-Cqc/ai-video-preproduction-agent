import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.context import ActorContext, OrganizationContext, TenantContext
from services.api.app.application.errors import ResourceConflict
from services.api.app.application.ingestion_services import BriefIngestionApplicationService
from services.api.app.application.repositories import AuditEventRepository
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import (
    AuditEvent,
    BriefIngestion,
    BriefIngestionOperation,
    BriefIngestionSourceType,
    BriefIngestionStatus,
    BriefSourceType,
)
from services.api.app.infrastructure.database import SessionFactory, create_session_factory
from services.api.app.infrastructure.repositories import SqlAlchemyBriefIngestionRepository
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
)


def _setup(session_factory: SessionFactory) -> tuple[TenantContext, UUID, UUID, UUID]:
    tenant = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory))
    actor = ActorContext("actor:owner", "ingestion-concurrency")
    organization = tenant.create_organization(actor, slug=f"org-{uuid4().hex[:8]}", name="Org")
    organization_context = OrganizationContext(
        actor.actor_subject, actor.correlation_id, organization.id
    )
    workspace = tenant.create_workspace(organization_context, slug="main", name="Main")
    context = TenantContext(
        actor.actor_subject, actor.correlation_id, organization.id, workspace.id
    )
    project = tenant.create_project(context, name="Project", description=None)
    content = cast(dict[str, object], json.loads(FIXTURE.read_text()))
    brief = BriefApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory)).create_brief(
        context,
        project.id,
        title="Brief",
        structured_content=content,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Initial",
    )
    return context, project.id, brief.brief.id, brief.current_version.id


def _reservation(context: TenantContext, project_id: UUID, key: str, digest: str) -> BriefIngestion:
    now = datetime.now(UTC)
    return BriefIngestion(
        id=uuid4(),
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        project_id=project_id,
        brief_id=None,
        brief_version_id=None,
        operation=BriefIngestionOperation.CREATE_VERSION,
        idempotency_key=key,
        source_type=BriefIngestionSourceType.API_STRUCTURED,
        source_reference=None,
        payload_digest=digest,
        schema_version="1.0.0",
        status=BriefIngestionStatus.RESERVED,
        rejection_code=None,
        rejection_details=None,
        submitted_by_actor_subject=context.actor_subject,
        submitted_at=now,
        completed_at=None,
        correlation_id=context.correlation_id,
        version=1,
    )


@pytest.mark.parametrize("loser_digest", ["a" * 64, "c" * 64])
def test_conflicting_reservation_waits_then_reads_accepted(
    persistence_session_factory: SessionFactory, clean_database: None, loser_digest: str
) -> None:
    del clean_database
    context, project_id, brief_id, version_id = _setup(persistence_session_factory)
    winner_ready, loser_started = Event(), Event()
    key, digest = "concurrent-accepted", "a" * 64

    def winner() -> None:
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyBriefIngestionRepository(session)
            reserved = repo.reserve(_reservation(context, project_id, key, digest))
            assert reserved is not None
            winner_ready.set()
            assert loser_started.wait(5)
            repo.finalize_accepted(
                reserved,
                brief_id=brief_id,
                brief_version_id=version_id,
                completed_at=datetime.now(UTC),
                expected_version=1,
            )
            session.commit()

    def loser() -> tuple[BriefIngestion | None, BriefIngestion | None]:
        assert winner_ready.wait(5)
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyBriefIngestionRepository(session)
            loser_started.set()
            reserved = repo.reserve(_reservation(context, project_id, key, loser_digest))
            existing = repo.get_by_idempotency_key(
                context.organization_id,
                context.workspace_id,
                project_id,
                BriefIngestionOperation.CREATE_VERSION,
                key,
            )
            session.commit()
            return reserved, existing

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner_future = pool.submit(winner)
        loser_future = pool.submit(loser)
        winner_future.result(timeout=10)
        reserved, existing = loser_future.result(timeout=10)
    assert reserved is None
    assert existing is not None and existing.status is BriefIngestionStatus.ACCEPTED
    assert existing.payload_digest == digest
    assert (existing.payload_digest == loser_digest) is (loser_digest == digest)


def test_rollback_releases_unique_reservation_to_loser(
    persistence_session_factory: SessionFactory, clean_database: None
) -> None:
    del clean_database
    context, project_id, _, _ = _setup(persistence_session_factory)
    winner_ready, loser_started = Event(), Event()
    key, digest = "concurrent-rollback", "b" * 64

    def winner() -> None:
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            repo = SqlAlchemyBriefIngestionRepository(session)
            assert repo.reserve(_reservation(context, project_id, key, digest)) is not None
            winner_ready.set()
            assert loser_started.wait(5)
            session.rollback()

    def loser() -> BriefIngestion | None:
        assert winner_ready.wait(5)
        with persistence_session_factory() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            loser_started.set()
            result = SqlAlchemyBriefIngestionRepository(session).reserve(
                _reservation(context, project_id, key, digest)
            )
            session.rollback()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner_future = pool.submit(winner)
        loser_future = pool.submit(loser)
        winner_future.result(timeout=10)
        reservation = loser_future.result(timeout=10)
    assert reservation is not None
    with persistence_session_factory() as session:
        assert (
            SqlAlchemyBriefIngestionRepository(session).get_by_idempotency_key(
                context.organization_id,
                context.workspace_id,
                project_id,
                BriefIngestionOperation.CREATE_VERSION,
                key,
            )
            is None
        )


@pytest.mark.parametrize("different_payload", [False, True])
def test_concurrent_application_requests_create_one_logical_mutation(
    test_database_url: str, clean_database: None, different_payload: bool
) -> None:
    del clean_database
    engine = create_engine(
        test_database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=5000"},
    )
    session_factory = create_session_factory(engine)
    context, project_id, _, _ = _setup(session_factory)
    barrier = Barrier(2)

    def request(title: str) -> tuple[str, bool | str]:
        barrier.wait(timeout=5)
        service = BriefIngestionApplicationService(lambda: SqlAlchemyUnitOfWork(session_factory))
        try:
            result = service.create_brief(
                context,
                project_id,
                idempotency_key="application-concurrent-key",
                title=title,
                structured_content=cast(dict[str, object], json.loads(FIXTURE.read_text())),
                source_type=BriefIngestionSourceType.API_STRUCTURED,
                source_reference=None,
                change_summary="Concurrent request",
            )
            return "result", result.replayed
        except ResourceConflict as error:
            return "error", error.code

    second_title = "Different Brief" if different_payload else "Concurrent Brief"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(request, "Concurrent Brief"),
            pool.submit(request, second_title),
        ]
        outcomes = [future.result(timeout=10) for future in futures]

    with engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_ingestions WHERE status = 'accepted'), "
                "(SELECT count(*) FROM briefs), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action = 'brief.ingestion_accepted')"
            )
        ).one()
        reserved = connection.scalar(
            text("SELECT count(*) FROM brief_ingestions WHERE status = 'reserved'")
        )
    engine.dispose()
    # _setup creates one baseline Brief; the two competing requests add exactly one more.
    assert tuple(counts) == (1, 2, 1)
    assert reserved == 0
    if different_payload:
        assert sorted(outcomes) == [
            ("error", "idempotency_conflict"),
            ("result", False),
        ]
    else:
        assert sorted(outcomes) == [("result", False), ("result", True)]


class CoordinatedFailingAuditRepository(AuditEventRepository):
    def __init__(self, winner_ready: Event, loser_started: Event) -> None:
        self.winner_ready = winner_ready
        self.loser_started = loser_started

    def append(self, event: AuditEvent) -> AuditEvent:
        del event
        self.winner_ready.set()
        assert self.loser_started.wait(5)
        raise RuntimeError("coordinated winner rollback")

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


class CoordinatedFailingAuditUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(
        self, session_factory: SessionFactory, winner_ready: Event, loser_started: Event
    ) -> None:
        super().__init__(session_factory)
        self.winner_ready = winner_ready
        self.loser_started = loser_started

    def __enter__(self) -> "CoordinatedFailingAuditUnitOfWork":
        super().__enter__()
        self.audit_events = CoordinatedFailingAuditRepository(self.winner_ready, self.loser_started)
        return self


def test_application_loser_takes_over_after_winner_rollback(
    persistence_session_factory: SessionFactory, clean_database: None, database_engine: Engine
) -> None:
    del clean_database
    context, project_id, _, _ = _setup(persistence_session_factory)
    winner_ready, loser_started = Event(), Event()

    def winner() -> None:
        service = BriefIngestionApplicationService(
            lambda: CoordinatedFailingAuditUnitOfWork(
                persistence_session_factory, winner_ready, loser_started
            )
        )
        with pytest.raises(RuntimeError, match="coordinated winner rollback"):
            service.create_brief(
                context,
                project_id,
                idempotency_key="rollback-takeover-key",
                title="Rollback Brief",
                structured_content=cast(dict[str, object], json.loads(FIXTURE.read_text())),
                source_type=BriefIngestionSourceType.API_STRUCTURED,
                source_reference=None,
                change_summary="Fail before commit",
            )

    def loser() -> bool:
        assert winner_ready.wait(5)
        loser_started.set()
        result = BriefIngestionApplicationService(
            lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
        ).create_brief(
            context,
            project_id,
            idempotency_key="rollback-takeover-key",
            title="Rollback Brief",
            structured_content=cast(dict[str, object], json.loads(FIXTURE.read_text())),
            source_type=BriefIngestionSourceType.API_STRUCTURED,
            source_reference=None,
            change_summary="Fail before commit",
        )
        return result.replayed

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner_future = pool.submit(winner)
        loser_future = pool.submit(loser)
        winner_future.result(timeout=10)
        assert loser_future.result(timeout=10) is False

    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_ingestions WHERE status = 'accepted'), "
                "(SELECT count(*) FROM brief_ingestions WHERE status = 'reserved'), "
                "(SELECT count(*) FROM audit_events WHERE action = 'brief.ingestion_accepted')"
            )
        ).one()
    assert tuple(counts) == (1, 0, 1)
