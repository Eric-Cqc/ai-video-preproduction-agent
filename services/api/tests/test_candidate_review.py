import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Barrier
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import Engine, inspect, text

from services.api.app.application.brief_extraction_services import StructuredBriefExtractionService
from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.candidate_review_services import (
    BriefCandidateReviewService,
    CandidateReviewResult,
)
from services.api.app.application.context import TenantContext
from services.api.app.application.errors import ResourceConflict
from services.api.app.application.model_provider import (
    DeterministicFakeProvider,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.domain import BriefCandidateRejectReason, BriefExtractionRun, BriefSourceType
from services.api.app.infrastructure.database import SessionFactory
from services.api.app.infrastructure.models import BriefVersionRecord
from services.api.app.infrastructure.uow import SqlAlchemyUnitOfWork
from services.api.tests.test_brief_extraction_foundation import FIXTURES, _source
from services.api.tests.test_source_object_transactions import _FailingAuditUoW, _FailureState


class _FailingRepository:
    def __init__(self, wrapped: object, method: str) -> None:
        self._wrapped = wrapped
        self._method = method

    def __getattr__(self, name: str) -> Any:
        if name == self._method:
            return self._fail
        return getattr(self._wrapped, name)

    @staticmethod
    def _fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("candidate review failpoint")


class _FailingCandidateReviewUoW(SqlAlchemyUnitOfWork):
    def __init__(self, session_factory: SessionFactory, point: str) -> None:
        super().__init__(session_factory)
        self.point = point

    def __enter__(self) -> "_FailingCandidateReviewUoW":
        super().__enter__()
        repository_name, method = self.point.split(".", maxsplit=1)
        wrapped = getattr(self, repository_name)
        setattr(self, repository_name, _FailingRepository(wrapped, method))
        return self


def _review_counts(database_engine: Engine) -> tuple[int, int, int, int, int]:
    with database_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_candidate_reviews), "
                "(SELECT count(*) FROM briefs), (SELECT count(*) FROM brief_versions), "
                "(SELECT count(*) FROM requirement_issues), "
                "(SELECT count(*) FROM audit_events WHERE action LIKE 'brief_candidate.%')"
            )
        ).one()
    return cast(tuple[int, int, int, int, int], tuple(row))


def _candidate(
    session_factory: SessionFactory, tmp_path: Path
) -> tuple[TenantContext, UUID, BriefExtractionRun]:
    context, project_id, asset_id, version_id, extraction_id = _source(session_factory, tmp_path)
    run = (
        StructuredBriefExtractionService(
            lambda: SqlAlchemyUnitOfWork(session_factory),
            DeterministicFakeProvider(
                ProviderOutcome(
                    ProviderOutcomeStatus.SUCCESS,
                    (FIXTURES / "valid-structured-brief-v1.json").read_text(),
                )
            ),
        )
        .extract(context, project_id, asset_id, version_id, extraction_id)
        .run
    )
    return context, project_id, run


def test_accept_creates_first_draft_and_replays(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    service = BriefCandidateReviewService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    first = service.accept(
        context,
        project_id,
        run.id,
        idempotency_key="review-first-accept",
        brief_id=None,
        expected_brief_version=None,
        expected_current_version_id=None,
        accepted_content=None,
        title="Human reviewed Brief",
    )
    replay = service.accept(
        context,
        project_id,
        run.id,
        idempotency_key="review-first-accept",
        brief_id=None,
        expected_brief_version=None,
        expected_current_version_id=None,
        accepted_content=None,
        title="Human reviewed Brief",
    )
    assert first.review.status.value == "accepted"
    assert first.review.brief_version_id is not None
    assert replay.replayed is True
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM brief_candidate_reviews")) == 1
        assert connection.scalar(text("SELECT count(*) FROM brief_versions")) == 1
        assert (
            connection.scalar(
                text("SELECT count(*) FROM audit_events WHERE action='brief_candidate.accepted'")
            )
            == 1
        )


def test_reject_is_terminal_and_does_not_create_brief(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    review = BriefCandidateReviewService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).reject(
        context,
        project_id,
        run.id,
        idempotency_key="review-reject-key",
        reason=BriefCandidateRejectReason.INCOMPLETE,
        note="Needs an operator rewrite",
    )
    assert review.review.status.value == "rejected"
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM briefs")) == 0
        assert connection.scalar(text("SELECT count(*) FROM brief_versions")) == 0


def test_same_key_with_changed_accept_content_conflicts(
    persistence_session_factory: SessionFactory, clean_database: None, tmp_path: Path
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    service = BriefCandidateReviewService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    service.accept(
        context,
        project_id,
        run.id,
        idempotency_key="review-content-key",
        brief_id=None,
        expected_brief_version=None,
        expected_current_version_id=None,
        accepted_content=None,
        title="Reviewed Brief",
    )
    changed_content = deepcopy(run.candidate_structured_brief)
    assert changed_content is not None
    changed_content["open_questions"] = ["A human changed this canonical request."]
    with pytest.raises(ResourceConflict):
        service.accept(
            context,
            project_id,
            run.id,
            idempotency_key="review-content-key",
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=changed_content,
            title="Reviewed Brief",
        )


def test_concurrent_same_key_accept_replays_once(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    service = BriefCandidateReviewService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    start = Barrier(2)

    def accept() -> CandidateReviewResult:
        start.wait(timeout=10)
        return service.accept(
            context,
            project_id,
            run.id,
            idempotency_key="concurrent-review-key",
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=None,
            title="Concurrent review",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result.replayed for result in results) == [False, True]
    assert len({result.review.brief_version_id for result in results}) == 1
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_candidate_reviews), "
                "(SELECT count(*) FROM brief_versions), "
                "(SELECT count(*) FROM audit_events "
                "WHERE action='brief_candidate.accepted'), "
                "(SELECT count(*) FROM brief_candidate_reviews WHERE status='reserved')"
            )
        ).one()
    assert counts == (1, 1, 1, 0)


def test_accept_audit_failure_rolls_back_review_and_brief(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    state = _FailureState(1)
    service = BriefCandidateReviewService(
        lambda: _FailingAuditUoW(persistence_session_factory, state)
    )
    with pytest.raises(RuntimeError, match="audit failure"):
        service.accept(
            context,
            project_id,
            run.id,
            idempotency_key="review-audit-failure",
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=None,
            title="Rollback review",
        )
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_candidate_reviews), "
                "(SELECT count(*) FROM briefs), (SELECT count(*) FROM brief_versions), "
                "(SELECT count(*) FROM requirement_issues), "
                "(SELECT count(*) FROM audit_events WHERE action='brief_candidate.accepted')"
            )
        ).one()
    assert counts == (0, 0, 0, 0, 0)


def test_concurrent_accept_and_reject_have_one_terminal_result(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    service = BriefCandidateReviewService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    start = Barrier(2)

    def accept() -> object:
        start.wait(timeout=10)
        return service.accept(
            context,
            project_id,
            run.id,
            idempotency_key="race-accept",
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=None,
            title="Race review",
        )

    def reject() -> object:
        start.wait(timeout=10)
        return service.reject(
            context,
            project_id,
            run.id,
            idempotency_key="race-reject",
            reason=BriefCandidateRejectReason.INACCURATE,
            note=None,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (pool.submit(accept), pool.submit(reject))
        outcomes: list[object] = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=15))
            except ResourceConflict as error:
                outcomes.append(error)
    assert sum(not isinstance(outcome, ResourceConflict) for outcome in outcomes) == 1
    with database_engine.connect() as connection:
        status = connection.scalar(text("SELECT status FROM brief_candidate_reviews"))
        versions = connection.scalar(text("SELECT count(*) FROM brief_versions"))
        reserved = connection.scalar(
            text("SELECT count(*) FROM brief_candidate_reviews WHERE status='reserved'")
        )
    assert status in {"accepted", "rejected"}
    assert versions == (1 if status == "accepted" else 0)
    assert reserved == 0


def test_concurrent_same_key_reject_replays_once(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    service = BriefCandidateReviewService(lambda: SqlAlchemyUnitOfWork(persistence_session_factory))
    start = Barrier(2)

    def reject() -> CandidateReviewResult:
        start.wait(timeout=10)
        return service.reject(
            context,
            project_id,
            run.id,
            idempotency_key="concurrent-reject-key",
            reason=BriefCandidateRejectReason.INCOMPLETE,
            note=None,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reject) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result.replayed for result in results) == [False, True]
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_candidate_reviews WHERE status='rejected'), "
                "(SELECT count(*) FROM audit_events WHERE action='brief_candidate.rejected'), "
                "(SELECT count(*) FROM brief_candidate_reviews WHERE status='reserved')"
            )
        ).one()
    assert counts == (1, 1, 0)


def test_accept_rollback_releases_reservation_for_a_later_winner(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    failing = BriefCandidateReviewService(
        lambda: _FailingAuditUoW(persistence_session_factory, _FailureState(1))
    )
    with pytest.raises(RuntimeError, match="audit failure"):
        failing.accept(
            context,
            project_id,
            run.id,
            idempotency_key="released-accept-key",
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=None,
            title="Released reservation",
        )
    succeeded = BriefCandidateReviewService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).accept(
        context,
        project_id,
        run.id,
        idempotency_key="released-accept-key",
        brief_id=None,
        expected_brief_version=None,
        expected_current_version_id=None,
        accepted_content=None,
        title="Released reservation",
    )
    assert succeeded.replayed is False
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_candidate_reviews WHERE status='accepted'), "
                "(SELECT count(*) FROM brief_candidate_reviews WHERE status='reserved'), "
                "(SELECT count(*) FROM brief_versions), "
                "(SELECT count(*) FROM audit_events WHERE action='brief_candidate.accepted')"
            )
        ).one()
    assert counts == (1, 0, 1, 1)


def test_reject_rollback_releases_reservation_for_a_later_winner(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    failing = BriefCandidateReviewService(
        lambda: _FailingAuditUoW(persistence_session_factory, _FailureState(1))
    )
    with pytest.raises(RuntimeError, match="audit failure"):
        failing.reject(
            context,
            project_id,
            run.id,
            idempotency_key="released-reject-key",
            reason=BriefCandidateRejectReason.INCOMPLETE,
            note=None,
        )
    succeeded = BriefCandidateReviewService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).reject(
        context,
        project_id,
        run.id,
        idempotency_key="released-reject-key",
        reason=BriefCandidateRejectReason.INCOMPLETE,
        note=None,
    )
    assert succeeded.replayed is False
    with database_engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM brief_candidate_reviews WHERE status='rejected'), "
                "(SELECT count(*) FROM brief_candidate_reviews WHERE status='reserved'), "
                "(SELECT count(*) FROM briefs), "
                "(SELECT count(*) FROM brief_versions), "
                "(SELECT count(*) FROM audit_events WHERE action='brief_candidate.rejected')"
            )
        ).one()
    assert counts == (1, 0, 0, 0, 1)


@pytest.mark.parametrize(
    "failure_point",
    [
        "briefs.add",
        "brief_versions.add",
        "requirement_issues.add",
        "brief_candidate_reviews.finalize",
        "audit_events.append",
    ],
)
def test_first_accept_failure_rolls_back_every_write(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
    failure_point: str,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    incomplete = json.loads((FIXTURES / "incomplete-structured-brief-v1.json").read_text())
    service = BriefCandidateReviewService(
        lambda: _FailingCandidateReviewUoW(persistence_session_factory, failure_point)
    )

    with pytest.raises(RuntimeError, match="candidate review failpoint"):
        service.accept(
            context,
            project_id,
            run.id,
            idempotency_key=f"first-accept-{failure_point}",
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=incomplete,
            title="Rollback matrix",
        )

    assert _review_counts(database_engine) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "failure_point",
    [
        "briefs.update",
        "brief_versions.add",
        "requirement_issues.add",
        "brief_candidate_reviews.finalize",
        "audit_events.append",
    ],
)
def test_successor_accept_failure_preserves_existing_brief_and_pointer(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
    failure_point: str,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    assert run.candidate_structured_brief is not None
    original = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).create_brief(
        context,
        project_id,
        title="Existing Brief",
        structured_content=run.candidate_structured_brief,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Rollback baseline",
    )
    incomplete = json.loads((FIXTURES / "incomplete-structured-brief-v1.json").read_text())
    service = BriefCandidateReviewService(
        lambda: _FailingCandidateReviewUoW(persistence_session_factory, failure_point)
    )

    with pytest.raises(RuntimeError, match="candidate review failpoint"):
        service.accept(
            context,
            project_id,
            run.id,
            idempotency_key=f"successor-accept-{failure_point}",
            brief_id=original.brief.id,
            expected_brief_version=original.brief.version,
            expected_current_version_id=original.current_version.id,
            accepted_content=incomplete,
            title=None,
        )

    assert _review_counts(database_engine) == (0, 1, 1, 0, 0)
    with database_engine.connect() as connection:
        persisted = connection.execute(
            text(
                "SELECT current_version_id, latest_version_number, version FROM briefs WHERE id=:id"
            ),
            {"id": original.brief.id},
        ).one()
    assert persisted == (original.current_version.id, 1, 1)


@pytest.mark.parametrize(
    "failure_point", ["brief_candidate_reviews.finalize", "audit_events.append"]
)
def test_reject_failure_rolls_back_reservation_and_audit(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    database_engine: Engine,
    tmp_path: Path,
    failure_point: str,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    service = BriefCandidateReviewService(
        lambda: _FailingCandidateReviewUoW(persistence_session_factory, failure_point)
    )

    with pytest.raises(RuntimeError, match="candidate review failpoint"):
        service.reject(
            context,
            project_id,
            run.id,
            idempotency_key=f"reject-{failure_point}",
            reason=BriefCandidateRejectReason.INACCURATE,
            note="Rollback matrix",
        )

    assert _review_counts(database_engine) == (0, 0, 0, 0, 0)


def test_review_request_digest_changes_for_every_semantic_accept_input() -> None:
    run_id = UUID("00000000-0000-0000-0000-000000000001")
    brief_id = UUID("00000000-0000-0000-0000-000000000002")
    version_id = UUID("00000000-0000-0000-0000-000000000003")
    base: dict[str, object] = {
        "run_id": str(run_id),
        "action": "accept",
        "brief_id": str(brief_id),
        "expected_brief_version": 4,
        "expected_current_version_id": str(version_id),
        "content": {"schema_version": "1.0.0", "open_questions": []},
        "reason": None,
        "note": None,
    }
    variants = []
    for field, value in (
        ("run_id", str(UUID("00000000-0000-0000-0000-000000000004"))),
        ("brief_id", str(UUID("00000000-0000-0000-0000-000000000005"))),
        ("expected_brief_version", 5),
        ("expected_current_version_id", str(UUID("00000000-0000-0000-0000-000000000006"))),
        ("content", {"schema_version": "1.0.0", "open_questions": ["changed"]}),
    ):
        changed = deepcopy(base)
        changed[field] = value
        variants.append(changed)
    digests = {BriefCandidateReviewService._digest(value) for value in [base, *variants]}
    assert len(digests) == 1 + len(variants)


def test_review_request_digest_changes_for_every_semantic_reject_input() -> None:
    base: dict[str, object] = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "action": "reject",
        "brief_id": None,
        "expected_brief_version": None,
        "expected_current_version_id": None,
        "content": None,
        "reason": "inaccurate",
        "note": None,
    }
    variants = []
    for field, value in (
        ("run_id", "00000000-0000-0000-0000-000000000002"),
        ("reason", "incomplete"),
        ("note", "Human supplied note"),
    ):
        changed = deepcopy(base)
        changed[field] = value
        variants.append(changed)
    digests = {BriefCandidateReviewService._digest(value) for value in [base, *variants]}
    assert len(digests) == 1 + len(variants)


def test_accepting_successor_keeps_every_approved_predecessor_column_immutable(
    persistence_session_factory: SessionFactory,
    clean_database: None,
    tmp_path: Path,
) -> None:
    del clean_database
    context, project_id, run = _candidate(persistence_session_factory, tmp_path)
    assert run.candidate_structured_brief is not None
    brief_service = BriefApplicationService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    )
    created = brief_service.create_brief(
        context,
        project_id,
        title="Approved predecessor",
        structured_content=run.candidate_structured_brief,
        source_type=BriefSourceType.MANUAL,
        source_reference=None,
        change_summary="Immutable baseline",
    )
    submitted = brief_service.submit(
        context,
        project_id,
        created.brief.id,
        expected_brief_version=created.brief.version,
        expected_current_version_id=created.current_version.id,
    )
    approved = brief_service.approve(
        context,
        project_id,
        created.brief.id,
        expected_brief_version=submitted.brief.version,
        expected_current_version_id=created.current_version.id,
    )
    column_keys = [column.key for column in inspect(BriefVersionRecord).mapper.column_attrs]
    with persistence_session_factory() as session:
        predecessor = session.get(BriefVersionRecord, created.current_version.id)
        assert predecessor is not None
        before = {key: getattr(predecessor, key) for key in column_keys}

    result = BriefCandidateReviewService(
        lambda: SqlAlchemyUnitOfWork(persistence_session_factory)
    ).accept(
        context,
        project_id,
        run.id,
        idempotency_key="approved-predecessor-successor",
        brief_id=approved.brief.id,
        expected_brief_version=approved.brief.version,
        expected_current_version_id=approved.current_version.id,
        accepted_content=None,
        title=None,
    )
    assert result.review.brief_version_id != approved.current_version.id
    with persistence_session_factory() as session:
        predecessor = session.get(BriefVersionRecord, created.current_version.id)
        assert predecessor is not None
        after = {key: getattr(predecessor, key) for key in column_keys}
    assert after == before
