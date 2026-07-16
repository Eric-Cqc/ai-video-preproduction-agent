import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.context import TenantContext
from services.api.app.application.errors import (
    InvalidRequest,
    PermissionDenied,
    ResourceConflict,
    ResourceNotFound,
)
from services.api.app.application.services import (
    MUTATION_ROLES,
    READ_ROLES,
    Clock,
    IdFactory,
    utc_now,
)
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    AuditEvent,
    Brief,
    BriefCandidateRejectReason,
    BriefCandidateReview,
    BriefCandidateReviewAction,
    BriefCandidateReviewStatus,
    BriefExtractionRun,
    BriefExtractionRunStatus,
    BriefSourceType,
    BriefStatus,
    BriefVersion,
    BriefVersionLifecycle,
)


@dataclass(frozen=True, slots=True)
class CandidateReviewResult:
    review: BriefCandidateReview
    replayed: bool


class BriefCandidateReviewService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.clock = clock
        self.id_factory = id_factory
        self._briefs = BriefApplicationService(uow_factory, clock=clock, id_factory=id_factory)

    def get_run(self, context: TenantContext, project_id: UUID, run_id: UUID) -> BriefExtractionRun:
        with self.uow_factory() as uow:
            self._briefs._require_project_access(uow, context, project_id, READ_ROLES)
            run = uow.brief_extraction_runs.get(
                context.organization_id, context.workspace_id, project_id, run_id
            )
            if run is None:
                raise ResourceNotFound("candidate is not accessible")
            return run

    def get_review(
        self, context: TenantContext, project_id: UUID, run_id: UUID
    ) -> BriefCandidateReview | None:
        with self.uow_factory() as uow:
            self._briefs._require_project_access(uow, context, project_id, READ_ROLES)
            return uow.brief_candidate_reviews.get_for_run(
                context.organization_id, context.workspace_id, project_id, run_id
            )

    def accept(
        self,
        context: TenantContext,
        project_id: UUID,
        run_id: UUID,
        *,
        idempotency_key: str,
        brief_id: UUID | None,
        expected_brief_version: int | None,
        expected_current_version_id: UUID | None,
        accepted_content: dict[str, object] | None,
        title: str | None,
    ) -> CandidateReviewResult:
        return self._review(
            context,
            project_id,
            run_id,
            BriefCandidateReviewAction.ACCEPT,
            idempotency_key,
            brief_id=brief_id,
            expected_brief_version=expected_brief_version,
            expected_current_version_id=expected_current_version_id,
            accepted_content=accepted_content,
            title=title,
            rejection_reason=None,
            rejection_note=None,
        )

    def reject(
        self,
        context: TenantContext,
        project_id: UUID,
        run_id: UUID,
        *,
        idempotency_key: str,
        reason: BriefCandidateRejectReason,
        note: str | None,
    ) -> CandidateReviewResult:
        if note is not None and (len(note) > 500 or any(ord(char) < 32 for char in note)):
            raise InvalidRequest("rejection note is invalid")
        return self._review(
            context,
            project_id,
            run_id,
            BriefCandidateReviewAction.REJECT,
            idempotency_key,
            brief_id=None,
            expected_brief_version=None,
            expected_current_version_id=None,
            accepted_content=None,
            title=None,
            rejection_reason=reason,
            rejection_note=note,
        )

    def _review(
        self,
        context: TenantContext,
        project_id: UUID,
        run_id: UUID,
        action: BriefCandidateReviewAction,
        idempotency_key: str,
        *,
        brief_id: UUID | None,
        expected_brief_version: int | None,
        expected_current_version_id: UUID | None,
        accepted_content: dict[str, object] | None,
        title: str | None,
        rejection_reason: BriefCandidateRejectReason | None,
        rejection_note: str | None,
    ) -> CandidateReviewResult:
        now = self.clock()
        with self.uow_factory() as uow:
            self._briefs._require_project_access(uow, context, project_id, READ_ROLES, mutable=True)
            membership = uow.memberships.find_effective(
                context.organization_id, context.workspace_id, context.actor_subject
            )
            if membership is None or membership.role not in MUTATION_ROLES:
                raise PermissionDenied("candidate review mutation is not permitted")
            run = uow.brief_extraction_runs.get(
                context.organization_id, context.workspace_id, project_id, run_id
            )
            if (
                run is None
                or run.status is not BriefExtractionRunStatus.HUMAN_REVIEW_REQUIRED
                or run.candidate_structured_brief is None
                or run.candidate_digest is None
            ):
                raise ResourceNotFound("reviewable candidate is not accessible")
            content = accepted_content or run.candidate_structured_brief
            if action is BriefCandidateReviewAction.ACCEPT:
                self._briefs._validate_content(content)
            digest = self._digest(
                {
                    "run_id": str(run_id),
                    "action": action.value,
                    "brief_id": str(brief_id) if brief_id else None,
                    "expected_brief_version": expected_brief_version,
                    "expected_current_version_id": str(expected_current_version_id)
                    if expected_current_version_id
                    else None,
                    "content": content if action is BriefCandidateReviewAction.ACCEPT else None,
                    "reason": rejection_reason.value if rejection_reason else None,
                    "note": rejection_note,
                }
            )
            reserved = BriefCandidateReview(
                id=self.id_factory(),
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                brief_extraction_run_id=run_id,
                action=action,
                status=BriefCandidateReviewStatus.RESERVED,
                idempotency_key=idempotency_key,
                request_digest=digest,
                candidate_digest=run.candidate_digest,
                accepted_content_digest=None,
                accepted_content_modified=None,
                brief_id=None,
                brief_version_id=None,
                rejection_reason=None,
                rejection_note=None,
                submitted_by_actor_subject=context.actor_subject,
                submitted_at=now,
                completed_at=None,
                correlation_id=context.correlation_id,
                version=1,
            )
            review = uow.brief_candidate_reviews.reserve(reserved)
            if review is None:
                existing = uow.brief_candidate_reviews.get_by_key(
                    context.organization_id,
                    context.workspace_id,
                    project_id,
                    action.value,
                    idempotency_key,
                )
                if existing is not None:
                    if existing.request_digest != digest:
                        raise ResourceConflict(
                            "idempotency key was used for a different review request",
                            code="idempotency_conflict",
                        )
                    if existing.status is BriefCandidateReviewStatus.RESERVED:
                        raise ResourceConflict("candidate review is not complete")
                    return CandidateReviewResult(existing, True)
                terminal = uow.brief_candidate_reviews.get_for_run(
                    context.organization_id, context.workspace_id, project_id, run_id
                )
                if terminal is not None:
                    raise ResourceConflict(
                        "candidate already has a terminal review", code="candidate_review_conflict"
                    )
                raise ResourceConflict("candidate review reservation could not be resolved")
            if action is BriefCandidateReviewAction.REJECT:
                if rejection_reason is None:
                    raise InvalidRequest("rejection reason is required")
                final = replace(
                    review,
                    status=BriefCandidateReviewStatus.REJECTED,
                    rejection_reason=rejection_reason,
                    rejection_note=rejection_note,
                    completed_at=now,
                    version=2,
                )
                saved = uow.brief_candidate_reviews.finalize(final, expected_version=1)
                uow.audit_events.append(
                    self._audit(
                        context,
                        run_id,
                        "brief_candidate.rejected",
                        {"review_id": str(saved.id), "reason": rejection_reason.value},
                    )
                )
                return CandidateReviewResult(saved, False)
            saved_brief, saved_version = self._accept_content(
                uow,
                context,
                project_id,
                brief_id,
                expected_brief_version,
                expected_current_version_id,
                content,
                title,
                now,
            )
            final = replace(
                review,
                status=BriefCandidateReviewStatus.ACCEPTED,
                accepted_content_digest=self._content_digest(content),
                accepted_content_modified=content != run.candidate_structured_brief,
                brief_id=saved_brief.id,
                brief_version_id=saved_version.id,
                completed_at=now,
                version=2,
            )
            saved = uow.brief_candidate_reviews.finalize(final, expected_version=1)
            uow.audit_events.append(
                self._audit(
                    context,
                    run_id,
                    "brief_candidate.accepted",
                    {
                        "review_id": str(saved.id),
                        "brief_id": str(saved_brief.id),
                        "brief_version_id": str(saved_version.id),
                        "whether_modified": saved.accepted_content_modified,
                    },
                )
            )
            return CandidateReviewResult(saved, False)

    def _accept_content(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        brief_id: UUID | None,
        expected_version: int | None,
        expected_current: UUID | None,
        content: dict[str, object],
        title: str | None,
        now: datetime,
    ) -> tuple[Brief, BriefVersion]:
        if brief_id is None:
            if uow.briefs.list(context.organization_id, context.workspace_id, project_id):
                raise InvalidRequest("brief_id is required when the project already has a Brief")
            if title is None or not title.strip():
                raise InvalidRequest("title is required when accepting the first Brief")
            new_brief_id, new_version_id = self.id_factory(), self.id_factory()
            brief = Brief(
                new_brief_id,
                context.organization_id,
                context.workspace_id,
                project_id,
                title,
                BriefStatus.DRAFT,
                new_version_id,
                1,
                context.actor_subject,
                now,
                now,
                1,
            )
            version = self._briefs._new_version_entity(
                context,
                project_id,
                new_brief_id,
                new_version_id,
                version_number=1,
                structured_content=content,
                source_type=BriefSourceType.IMPORTED_STRUCTURED,
                source_reference=None,
                change_summary="Accepted human review candidate",
                supersedes_version_id=None,
                now=now,
            )
            saved_brief, saved_version = uow.briefs.add(brief), uow.brief_versions.add(version)
        else:
            if expected_version is None or expected_current is None:
                raise InvalidRequest("expected Brief version and current version are required")
            current = self._briefs._require_brief(uow, context, project_id, brief_id)
            if current.current_version_id != expected_current:
                raise ResourceConflict("Brief current version changed", code="version_conflict")
            predecessor = self._briefs._require_version(
                uow, context, project_id, current, expected_current
            )
            updated = current.new_version(
                expected_version=expected_version, new_version_id=self.id_factory(), now=now
            )
            saved_brief = uow.briefs.update(
                updated,
                expected_version=expected_version,
                expected_current_version_id=expected_current,
            )
            if predecessor.lifecycle_state is not BriefVersionLifecycle.APPROVED:
                uow.brief_versions.supersede(predecessor.supersede())
            version = self._briefs._new_version_entity(
                context,
                project_id,
                brief_id,
                saved_brief.current_version_id,
                version_number=saved_brief.latest_version_number,
                structured_content=content,
                source_type=BriefSourceType.IMPORTED_STRUCTURED,
                source_reference=None,
                change_summary="Accepted human review candidate",
                supersedes_version_id=predecessor.id,
                now=now,
            )
            saved_version = uow.brief_versions.add(version)
        self._briefs._add_detected_issues(uow, context, saved_version, now)
        return saved_brief, saved_version

    def _audit(
        self, context: TenantContext, run_id: UUID, action: str, payload: dict[str, object]
    ) -> AuditEvent:
        return AuditEvent(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            context.actor_subject,
            "brief_extraction_run",
            run_id,
            action,
            payload,
            self.clock(),
            context.correlation_id,
            None,
        )

    @staticmethod
    def _digest(value: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()

    @classmethod
    def _content_digest(cls, value: dict[str, object]) -> str:
        return cls._digest(value)
