import json
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.ingestion_services import BriefIngestionApplicationService
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import (
    BriefIngestion,
    BriefIngestionSourceType,
    BriefSourceType,
    RequirementIssue,
    VersionConflict,
)
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.repositories import (
    SqlAlchemyBriefIngestionRepository,
    SqlAlchemyRequirementIssueRepository,
)
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_persistence import FailingAuditUnitOfWork, bootstrap

FIXTURES = Path(__file__).resolve().parents[3] / "packages/test-fixtures/brief"


class FailingFinalizeRepository(SqlAlchemyBriefIngestionRepository):
    def finalize_accepted(
        self,
        ingestion: BriefIngestion,
        *,
        brief_id: UUID,
        brief_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> BriefIngestion:
        del ingestion, brief_id, brief_version_id, completed_at, expected_version
        raise RuntimeError("simulated finalize failure")


class FailingFinalizeUnitOfWork(SqlAlchemyUnitOfWork):
    def __enter__(self) -> "FailingFinalizeUnitOfWork":
        super().__enter__()
        assert self.session is not None
        self.brief_ingestions = FailingFinalizeRepository(self.session)
        return self


class FailingIssueRepository(SqlAlchemyRequirementIssueRepository):
    def add(self, issue: RequirementIssue) -> RequirementIssue:
        del issue
        raise RuntimeError("simulated issue failure")


class FailingIssueUnitOfWork(SqlAlchemyUnitOfWork):
    def __enter__(self) -> "FailingIssueUnitOfWork":
        super().__enter__()
        assert self.session is not None
        self.requirement_issues = FailingIssueRepository(self.session)
        return self


def _content(name: str = "valid-structured-brief-v1.json") -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / name).read_text()))


def _counts(engine: Engine) -> tuple[int, int, int, int]:
    with engine.connect() as connection:
        return cast(
            tuple[int, int, int, int],
            connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM brief_ingestions), "
                    "(SELECT count(*) FROM briefs), (SELECT count(*) FROM brief_versions), "
                    "(SELECT count(*) FROM audit_events WHERE action = 'brief.ingestion_accepted')"
                )
            ).one(),
        )


@pytest.mark.parametrize(
    "uow_type,error",
    [
        (FailingAuditUnitOfWork, "simulated audit failure"),
        (FailingFinalizeUnitOfWork, "simulated finalize failure"),
        (FailingIssueUnitOfWork, "simulated issue failure"),
    ],
)
def test_ingestion_failure_rolls_back_reservation_and_mutation(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    uow_type: type[SqlAlchemyUnitOfWork],
    error: str,
) -> None:
    del clean_database
    tenant = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    _, context = bootstrap(tenant)
    project = tenant.create_project(context, name="Project", description=None)
    service = BriefIngestionApplicationService(lambda: uow_type(persistence_session_factory))
    with pytest.raises(RuntimeError, match=error):
        service.create_brief(
            context,
            project.id,
            idempotency_key=f"rollback-{error}",
            title="Brief",
            structured_content=_content(
                "incomplete-structured-brief-v1.json"
                if uow_type is FailingIssueUnitOfWork
                else "valid-structured-brief-v1.json"
            ),
            source_type=BriefIngestionSourceType.API_STRUCTURED,
            source_reference=None,
            change_summary="Rollback proof",
        )
    assert _counts(database_engine) == (0, 0, 0, 0)


def test_stale_cas_rolls_back_reservation(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
) -> None:
    del clean_database
    tenant = TenantApplicationService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    _, context = bootstrap(tenant)
    project = tenant.create_project(context, name="Project", description=None)
    brief = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).create_brief(
        context,
        project.id,
        title="Brief",
        structured_content=_content(),
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Initial",
    )
    service = BriefIngestionApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    with pytest.raises(VersionConflict):
        service.create_version(
            context,
            project.id,
            brief.brief.id,
            idempotency_key="stale-new-key",
            expected_brief_version=99,
            expected_current_version_id=brief.current_version.id,
            source_version_id=brief.current_version.id,
            structured_content=_content(),
            source_type=BriefIngestionSourceType.API_STRUCTURED,
            source_reference=None,
            change_summary="Stale",
        )
    counts = _counts(database_engine)
    assert counts[0] == 0
    assert counts[1:] == (1, 1, 0)
