import asyncio
import csv
import hashlib
import io
import json
import zipfile
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

from foundation_contracts import validate_script, validate_shot_plan, validate_storyboard
from jsonschema import ValidationError

from services.api.app.application.brief_services import BriefApplicationService
from services.api.app.application.context import TenantContext
from services.api.app.application.errors import (
    InvalidRequest,
    PermissionDenied,
    ResourceConflict,
    ResourceNotFound,
    StorageUnavailable,
)
from services.api.app.application.services import (
    MUTATION_ROLES,
    READ_ROLES,
    Clock,
    IdFactory,
    utc_now,
)
from services.api.app.application.storage import StorageError, StoragePort
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    ArtifactRevisionLink,
    AuditEvent,
    CreativeRunStatus,
    DeliveryExportFile,
    DeliveryOperation,
    DeliveryOperationStatus,
    DeliveryOperationType,
    DeliveryPackage,
    DeliveryPackageVersion,
    PlanningReview,
    PlanningReviewOutcome,
    PlanningRevisionRequest,
    ReviewArtifactType,
    RevisionRequestStatus,
    ScriptVersion,
    ShotPlanVersion,
    StoryboardVersion,
)

UnitOfWorkFactory = Callable[[], UnitOfWork]
SCHEMA_VERSION = "delivery-package-v1"
MAX_EXPORT_BYTES = 10 * 1024 * 1024
EXPORT_FORMATS = frozenset(
    {
        "manifest.json",
        "script.json",
        "storyboard.json",
        "shot-plan.json",
        "shot-plan.csv",
        "README.txt",
        "delivery-package.zip",
    }
)
SCRIPT_REVISION_MODES = frozenset(
    {
        "valid",
        "malformed",
        "schema_invalid",
        "duration_invalid",
        "refusal",
        "timeout",
        "provider_error",
    }
)
STORYBOARD_REVISION_MODES = frozenset(
    {
        "valid",
        "scene_mismatch",
        "duration_invalid",
        "schema_invalid",
        "refusal",
        "timeout",
        "provider_error",
    }
)
SHOT_PLAN_REVISION_MODES = frozenset(
    {
        "valid",
        "shot_order_invalid",
        "scene_coverage_invalid",
        "continuity_invalid",
        "duration_invalid",
        "schema_invalid",
        "refusal",
        "timeout",
        "provider_error",
    }
)


@dataclass(frozen=True, slots=True)
class ReviewResult:
    review: PlanningReview
    revision_request: PlanningRevisionRequest | None
    replayed: bool


@dataclass(frozen=True, slots=True)
class RevisionResult:
    request: PlanningRevisionRequest
    successor_script_version_id: UUID | None
    successor_storyboard_version_id: UUID | None
    successor_shot_plan_version_id: UUID | None
    replayed: bool


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    package: DeliveryPackage
    version: DeliveryPackageVersion
    replayed: bool


@dataclass(frozen=True, slots=True)
class ExportResult:
    file: DeliveryExportFile
    replayed: bool


class ReviewRevisionDeliveryApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        storage: StoragePort,
        *,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.storage = storage
        self.clock = clock
        self.id_factory = id_factory
        self._briefs = BriefApplicationService(uow_factory, clock=clock, id_factory=id_factory)

    def submit_review(
        self,
        context: TenantContext,
        project_id: UUID,
        *,
        artifact_type: ReviewArtifactType,
        script_version_id: UUID | None,
        storyboard_version_id: UUID | None,
        shot_plan_version_id: UUID | None,
        outcome: PlanningReviewOutcome,
        summary: str,
        requested_changes: dict[str, object],
        idempotency_key: str,
    ) -> ReviewResult:
        self._validate_review_input(
            artifact_type,
            outcome,
            summary,
            requested_changes,
            script_version_id,
            storyboard_version_id,
            shot_plan_version_id,
        )
        with self.uow_factory() as uow:
            artifacts = self._load_review_artifacts(
                uow,
                context,
                project_id,
                artifact_type,
                script_version_id,
                storyboard_version_id,
                shot_plan_version_id,
            )
            digest = _digest(
                {
                    "scope": _scope(context, project_id),
                    "artifact_type": artifact_type.value,
                    "script_version_id": str(script_version_id) if script_version_id else None,
                    "storyboard_version_id": str(storyboard_version_id)
                    if storyboard_version_id
                    else None,
                    "shot_plan_version_id": str(shot_plan_version_id)
                    if shot_plan_version_id
                    else None,
                    "content_digests": _artifact_digests(artifacts),
                    "outcome": outcome.value,
                    "summary": summary,
                    "requested_changes": requested_changes,
                }
            )
            existing = self._resolve_operation(
                uow,
                context,
                project_id,
                DeliveryOperationType.SUBMIT_PLANNING_REVIEW,
                idempotency_key,
                digest,
            )
            if existing is not None:
                review = self._require_review(uow, context, project_id, existing.outcome_review_id)
                replay_revision = (
                    self._require_revision(
                        uow, context, project_id, existing.outcome_revision_request_id
                    )
                    if existing.outcome_revision_request_id is not None
                    else None
                )
                return ReviewResult(review, replay_revision, True)
            self._require_mutation(uow, context, project_id)
            round_number = uow.planning_reviews.next_round(
                context.organization_id,
                context.workspace_id,
                project_id,
                artifact_type,
                script_version_id,
                storyboard_version_id,
                shot_plan_version_id,
            )
            now = self.clock()
            review = PlanningReview(
                id=self.id_factory(),
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                artifact_type=artifact_type,
                script_version_id=script_version_id,
                storyboard_version_id=storyboard_version_id,
                shot_plan_version_id=shot_plan_version_id,
                review_round=round_number,
                outcome=outcome,
                summary=summary,
                requested_changes=requested_changes,
                reviewed_by_actor_subject=context.actor_subject,
                reviewed_at=now,
                correlation_id=context.correlation_id,
                created_at=now,
            )
            reservation = self._reserve(
                context,
                project_id,
                DeliveryOperationType.SUBMIT_PLANNING_REVIEW,
                idempotency_key,
                digest,
            )
            won = uow.delivery_operations.reserve(reservation)
            if won is None:
                existing = self._resolve_operation(
                    uow,
                    context,
                    project_id,
                    DeliveryOperationType.SUBMIT_PLANNING_REVIEW,
                    idempotency_key,
                    digest,
                )
                if existing is None:
                    raise ResourceConflict("review reservation could not be resolved")
                replay_revision = (
                    self._require_revision(
                        uow, context, project_id, existing.outcome_revision_request_id
                    )
                    if existing.outcome_revision_request_id is not None
                    else None
                )
                return ReviewResult(
                    self._require_review(uow, context, project_id, existing.outcome_review_id),
                    replay_revision,
                    True,
                )
            uow.planning_reviews.add(review)
            revision_request: PlanningRevisionRequest | None = None
            if outcome is PlanningReviewOutcome.REVISION_REQUESTED:
                revision_request = self._new_revision_request(
                    context, project_id, review, requested_changes, artifacts
                )
                uow.planning_revision_requests.add(revision_request)
            accepted = replace(
                won,
                status=DeliveryOperationStatus.ACCEPTED,
                outcome_review_id=review.id,
                outcome_revision_request_id=revision_request.id if revision_request else None,
                completed_at=now,
                version=2,
            )
            uow.delivery_operations.finalize_accepted(accepted, expected_version=1)
            uow.audit_events.append(
                self._audit(
                    context,
                    review.id,
                    "planning_review.submitted",
                    {
                        "review_id": str(review.id),
                        "artifact_type": artifact_type.value,
                        "outcome": outcome.value,
                        "review_round": round_number,
                    },
                )
            )
            if revision_request is not None:
                uow.audit_events.append(
                    self._audit(
                        context,
                        revision_request.id,
                        "planning_revision.requested",
                        {
                            "revision_request_id": str(revision_request.id),
                            "review_id": str(review.id),
                            "artifact_type": artifact_type.value,
                        },
                    )
                )
            return ReviewResult(review, revision_request, False)

    def get_review(
        self, context: TenantContext, project_id: UUID, review_id: UUID
    ) -> PlanningReview:
        with self.uow_factory() as uow:
            self._require_read(uow, context, project_id)
            return self._require_review(uow, context, project_id, review_id)

    def list_reviews(self, context: TenantContext, project_id: UUID) -> list[PlanningReview]:
        with self.uow_factory() as uow:
            self._require_read(uow, context, project_id)
            return uow.planning_reviews.list(
                context.organization_id, context.workspace_id, project_id
            )

    def get_revision_request(
        self, context: TenantContext, project_id: UUID, request_id: UUID
    ) -> PlanningRevisionRequest:
        with self.uow_factory() as uow:
            self._require_read(uow, context, project_id)
            return self._require_revision(uow, context, project_id, request_id)

    def complete_revision(
        self,
        context: TenantContext,
        project_id: UUID,
        request_id: UUID,
        *,
        provider_mode: str = "valid",
        idempotency_key: str,
    ) -> RevisionResult:
        with self.uow_factory() as uow:
            request = self._require_revision(uow, context, project_id, request_id)
            mode_set = _mode_set(request.artifact_type)
            if provider_mode not in mode_set:
                raise InvalidRequest("revision mode is not permitted", code="invalid_provider_mode")
            digest = _digest(
                {
                    "scope": _scope(context, project_id),
                    "request_id": str(request.id),
                    "request_digest": request.request_digest,
                    "provider_mode": provider_mode,
                }
            )
            existing = self._resolve_operation(
                uow,
                context,
                project_id,
                DeliveryOperationType.COMPLETE_REVISION_REQUEST,
                idempotency_key,
                digest,
            )
            if existing is not None:
                return RevisionResult(
                    request,
                    request.successor_script_version_id,
                    request.successor_storyboard_version_id,
                    request.successor_shot_plan_version_id,
                    True,
                )
            self._require_mutation(uow, context, project_id)
            if request.status is not RevisionRequestStatus.OPEN:
                raise ResourceConflict("revision request is not open")
            review = self._require_review(uow, context, project_id, request.review_id)
            if review.outcome is not PlanningReviewOutcome.REVISION_REQUESTED:
                raise ResourceConflict("revision request is not actionable")
            reservation = self._reserve(
                context,
                project_id,
                DeliveryOperationType.COMPLETE_REVISION_REQUEST,
                idempotency_key,
                digest,
            )
            won = uow.delivery_operations.reserve(reservation)
            if won is None:
                existing = self._resolve_operation(
                    uow,
                    context,
                    project_id,
                    DeliveryOperationType.COMPLETE_REVISION_REQUEST,
                    idempotency_key,
                    digest,
                )
                if existing is None:
                    raise ResourceConflict("revision reservation could not be resolved")
                return RevisionResult(
                    request,
                    request.successor_script_version_id,
                    request.successor_storyboard_version_id,
                    request.successor_shot_plan_version_id,
                    True,
                )
            successors = self._create_successors(uow, context, project_id, request, provider_mode)
            now = self.clock()
            completed = replace(
                request,
                status=RevisionRequestStatus.COMPLETED,
                completed_at=now,
                successor_script_version_id=successors[0],
                successor_storyboard_version_id=successors[1],
                successor_shot_plan_version_id=successors[2],
                version=request.version + 1,
            )
            uow.planning_revision_requests.update_completed(
                completed, expected_version=request.version
            )
            accepted = replace(
                won,
                status=DeliveryOperationStatus.ACCEPTED,
                outcome_revision_request_id=request.id,
                completed_at=now,
                version=2,
            )
            uow.delivery_operations.finalize_accepted(accepted, expected_version=1)
            uow.audit_events.append(
                self._audit(
                    context,
                    request.id,
                    "planning_revision.completed",
                    {
                        "revision_request_id": str(request.id),
                        "artifact_type": request.artifact_type.value,
                        "successor_count": sum(item is not None for item in successors),
                    },
                )
            )
            return RevisionResult(completed, successors[0], successors[1], successors[2], False)

    def cancel_revision(
        self, context: TenantContext, project_id: UUID, request_id: UUID, *, idempotency_key: str
    ) -> PlanningRevisionRequest:
        with self.uow_factory() as uow:
            request = self._require_revision(uow, context, project_id, request_id)
            digest = _digest(
                {
                    "scope": _scope(context, project_id),
                    "request_id": str(request.id),
                    "action": "cancel",
                }
            )
            existing = self._resolve_operation(
                uow,
                context,
                project_id,
                DeliveryOperationType.CREATE_REVISION_REQUEST,
                idempotency_key,
                digest,
            )
            if existing is not None:
                return self._require_revision(uow, context, project_id, request_id)
            self._require_mutation(uow, context, project_id)
            if request.status is not RevisionRequestStatus.OPEN:
                raise ResourceConflict("revision request is not open")
            reservation = self._reserve(
                context,
                project_id,
                DeliveryOperationType.CREATE_REVISION_REQUEST,
                idempotency_key,
                digest,
            )
            won = uow.delivery_operations.reserve(reservation)
            if won is None:
                return self._require_revision(uow, context, project_id, request_id)
            now = self.clock()
            cancelled = replace(
                request,
                status=RevisionRequestStatus.CANCELLED,
                completed_at=None,
                version=request.version + 1,
            )
            uow.planning_revision_requests.update_cancelled(
                cancelled, expected_version=request.version
            )
            accepted = replace(
                won,
                status=DeliveryOperationStatus.ACCEPTED,
                outcome_review_id=request.review_id,
                outcome_revision_request_id=request.id,
                completed_at=now,
                version=2,
            )
            uow.delivery_operations.finalize_accepted(accepted, expected_version=1)
            return cancelled

    def create_delivery_package(
        self,
        context: TenantContext,
        project_id: UUID,
        *,
        script_version_id: UUID,
        storyboard_version_id: UUID,
        shot_plan_version_id: UUID,
        approval_review_id: UUID,
        idempotency_key: str,
    ) -> DeliveryResult:
        with self.uow_factory() as uow:
            script, storyboard, shot_plan = self._load_bundle(
                uow,
                context,
                project_id,
                script_version_id,
                storyboard_version_id,
                shot_plan_version_id,
            )
            review = self._require_review(uow, context, project_id, approval_review_id)
            self._validate_bundle(script, storyboard, shot_plan, review)
            digest = _digest(
                {
                    "scope": _scope(context, project_id),
                    "script_version_id": str(script.id),
                    "storyboard_version_id": str(storyboard.id),
                    "shot_plan_version_id": str(shot_plan.id),
                    "approval_review_id": str(review.id),
                    "digests": [
                        script.content_digest,
                        storyboard.content_digest,
                        shot_plan.content_digest,
                    ],
                }
            )
            existing = self._resolve_operation(
                uow,
                context,
                project_id,
                DeliveryOperationType.CREATE_DELIVERY_PACKAGE,
                idempotency_key,
                digest,
            )
            if existing is not None:
                package = self._require_package(
                    uow, context, project_id, existing.outcome_delivery_package_id
                )
                version = self._require_package_version(
                    uow, context, project_id, existing.outcome_delivery_package_version_id
                )
                return DeliveryResult(package, version, True)
            self._require_mutation(uow, context, project_id)
            reservation = self._reserve(
                context,
                project_id,
                DeliveryOperationType.CREATE_DELIVERY_PACKAGE,
                idempotency_key,
                digest,
            )
            won = uow.delivery_operations.reserve(reservation)
            if won is None:
                raise ResourceConflict("delivery package reservation could not be resolved")
            now = self.clock()
            package_id = self.id_factory()
            version_id = self.id_factory()
            manifest = self._manifest(
                context, project_id, script, storyboard, shot_plan, review, version_id
            )
            package = DeliveryPackage(
                package_id,
                context.organization_id,
                context.workspace_id,
                project_id,
                version_id,
                context.actor_subject,
                now,
                1,
            )
            version = DeliveryPackageVersion(
                version_id,
                context.organization_id,
                context.workspace_id,
                project_id,
                package_id,
                1,
                script.id,
                storyboard.id,
                shot_plan.id,
                review.id,
                script.content_digest,
                storyboard.content_digest,
                shot_plan.content_digest,
                SCHEMA_VERSION,
                manifest,
                _digest(manifest),
                context.actor_subject,
                now,
                None,
            )
            uow.delivery_packages.add(package)
            uow.delivery_package_versions.add(version)
            accepted = replace(
                won,
                status=DeliveryOperationStatus.ACCEPTED,
                outcome_delivery_package_id=package.id,
                outcome_delivery_package_version_id=version.id,
                completed_at=now,
                version=2,
            )
            uow.delivery_operations.finalize_accepted(accepted, expected_version=1)
            uow.audit_events.append(
                self._audit(
                    context,
                    package.id,
                    "delivery_package.created",
                    {
                        "package_id": str(package.id),
                        "version_id": str(version.id),
                        "manifest_schema_version": SCHEMA_VERSION,
                        "artifact_count": 3,
                    },
                )
            )
            return DeliveryResult(package, version, False)

    def get_delivery_package(
        self, context: TenantContext, project_id: UUID, version_id: UUID
    ) -> DeliveryPackageVersion:
        with self.uow_factory() as uow:
            self._require_read(uow, context, project_id)
            return self._require_package_version(uow, context, project_id, version_id)

    def export_delivery_package(
        self,
        context: TenantContext,
        project_id: UUID,
        package_version_id: UUID,
        *,
        export_format: str,
        idempotency_key: str,
    ) -> ExportResult:
        if export_format not in EXPORT_FORMATS:
            raise InvalidRequest("export format is not permitted", code="invalid_export_format")
        staged_key: str | None = None
        final_key: str | None = None
        try:
            with self.uow_factory() as uow:
                version = self._require_package_version(
                    uow, context, project_id, package_version_id
                )
                digest = _digest(
                    {
                        "scope": _scope(context, project_id),
                        "package_version_id": str(version.id),
                        "manifest_digest": version.manifest_digest,
                        "format": export_format,
                    }
                )
                existing = self._resolve_operation(
                    uow,
                    context,
                    project_id,
                    DeliveryOperationType.EXPORT_DELIVERY_PACKAGE,
                    idempotency_key,
                    digest,
                )
                if existing is not None:
                    export = self._require_export(
                        uow, context, project_id, existing.outcome_export_file_id
                    )
                    return ExportResult(export, True)
                self._require_mutation(uow, context, project_id)
                reservation = self._reserve(
                    context,
                    project_id,
                    DeliveryOperationType.EXPORT_DELIVERY_PACKAGE,
                    idempotency_key,
                    digest,
                )
                won = uow.delivery_operations.reserve(reservation)
                if won is None:
                    raise ResourceConflict("export reservation could not be resolved")
                payload = self._export_bytes(uow, context, project_id, version, export_format)
                staged_key = self._stage(payload)
                final_key = self.storage.new_final_key()
                self.storage.finalize(staged_key, final_key)
                now = self.clock()
                export = DeliveryExportFile(
                    self.id_factory(),
                    context.organization_id,
                    context.workspace_id,
                    project_id,
                    version.id,
                    export_format,
                    _filename(export_format),
                    self.storage.adapter_name,
                    final_key,
                    hashlib.sha256(payload).hexdigest(),
                    len(payload),
                    now,
                )
                uow.delivery_export_files.add(export)
                accepted = replace(
                    won,
                    status=DeliveryOperationStatus.ACCEPTED,
                    outcome_export_file_id=export.id,
                    completed_at=now,
                    version=2,
                )
                uow.delivery_operations.finalize_accepted(accepted, expected_version=1)
                uow.audit_events.append(
                    self._audit(
                        context,
                        export.id,
                        "delivery_package.exported",
                        {
                            "export_id": str(export.id),
                            "package_version_id": str(version.id),
                            "format": export_format,
                            "byte_size": len(payload),
                        },
                    )
                )
                return ExportResult(export, False)
        except StorageError as error:
            if staged_key is not None:
                self._delete_quietly(staged_key)
            if final_key is not None:
                self._delete_quietly(final_key)
            raise StorageUnavailable("delivery export storage is unavailable") from error
        except BaseException:
            if staged_key is not None:
                self._delete_quietly(staged_key)
            if final_key is not None:
                self._delete_quietly(final_key)
            raise

    def read_export(
        self, context: TenantContext, project_id: UUID, export_id: UUID
    ) -> tuple[DeliveryExportFile, Iterable[bytes]]:
        with self.uow_factory() as uow:
            self._require_read(uow, context, project_id)
            export = self._require_export(uow, context, project_id, export_id)
        try:
            return export, self.storage.read(export.storage_key)
        except StorageError as error:
            raise StorageUnavailable("delivery export is unavailable") from error

    def list_exports(
        self, context: TenantContext, project_id: UUID, package_version_id: UUID
    ) -> list[DeliveryExportFile]:
        with self.uow_factory() as uow:
            self._require_read(uow, context, project_id)
            self._require_package_version(uow, context, project_id, package_version_id)
            return uow.delivery_export_files.list_for_package_version(
                context.organization_id, context.workspace_id, project_id, package_version_id
            )

    def _create_successors(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        request: PlanningRevisionRequest,
        mode: str,
    ) -> tuple[UUID | None, UUID | None, UUID | None]:
        script_successor: ScriptVersion | None = None
        storyboard_successor: StoryboardVersion | None = None
        shot_successor: ShotPlanVersion | None = None
        if request.source_script_version_id is not None:
            source_script = self._require_script(
                uow, context, project_id, request.source_script_version_id
            )
            content = _revision_content(
                source_script.content, request.requested_changes, mode, "script"
            )
            self._validate_script(content)
            script_successor = self._successor_script(
                uow, context, project_id, source_script, content, request.id
            )
        if request.source_storyboard_version_id is not None:
            source_storyboard = self._require_storyboard(
                uow, context, project_id, request.source_storyboard_version_id
            )
            content = _revision_content(
                source_storyboard.content, request.requested_changes, mode, "storyboard"
            )
            script = script_successor or self._require_script(
                uow, context, project_id, source_storyboard.script_version_id
            )
            self._validate_storyboard(content, script)
            storyboard_successor = self._successor_storyboard(
                uow,
                context,
                project_id,
                source_storyboard,
                content,
                script_successor,
                request.id,
            )
        if request.source_shot_plan_version_id is not None:
            source_shot = self._require_shot_plan(
                uow, context, project_id, request.source_shot_plan_version_id
            )
            content = _revision_content(
                source_shot.content, request.requested_changes, mode, "shot_plan"
            )
            storyboard = storyboard_successor or self._require_storyboard(
                uow, context, project_id, source_shot.storyboard_version_id
            )
            script = script_successor or self._require_script(
                uow, context, project_id, source_shot.script_version_id
            )
            self._validate_shot_plan(content, storyboard, script)
            shot_successor = self._successor_shot_plan(
                uow,
                context,
                project_id,
                source_shot,
                content,
                storyboard_successor,
                script_successor,
                request.id,
            )
        if script_successor is None and request.source_script_version_id is not None:
            raise ResourceConflict("script successor was not created")
        return (
            script_successor.id if script_successor else None,
            storyboard_successor.id if storyboard_successor else None,
            shot_successor.id if shot_successor else None,
        )

    def _successor_script(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        source: ScriptVersion,
        content: dict[str, object],
        request_id: UUID,
    ) -> ScriptVersion:
        run = uow.script_runs.get(
            context.organization_id, context.workspace_id, project_id, source.script_run_id
        )
        if run is None or run.status is not CreativeRunStatus.COMPLETED:
            raise ResourceNotFound("script version is not accessible")
        now = self.clock()
        new_run = replace(
            run,
            id=self.id_factory(),
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            completed_at=now,
            version=1,
        )
        successor = replace(
            source,
            id=self.id_factory(),
            script_run_id=new_run.id,
            version_number=source.version_number + 1,
            content=content,
            content_digest=_content_digest(content),
            created_at=now,
        )
        uow.script_runs.add(new_run)
        uow.script_versions.add(successor)
        uow.artifact_revision_links.add(
            self._link(
                context,
                project_id,
                ReviewArtifactType.SCRIPT,
                source.id,
                successor.id,
                source.version_number,
                successor.version_number,
                request_id,
            )
        )
        return successor

    def _successor_storyboard(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        source: StoryboardVersion,
        content: dict[str, object],
        script_successor: ScriptVersion | None,
        request_id: UUID,
    ) -> StoryboardVersion:
        run = uow.storyboard_runs.get(
            context.organization_id, context.workspace_id, project_id, source.storyboard_run_id
        )
        if run is None or run.status is not CreativeRunStatus.COMPLETED:
            raise ResourceNotFound("storyboard version is not accessible")
        now = self.clock()
        script_version_id = script_successor.id if script_successor else source.script_version_id
        script_run_id = script_successor.script_run_id if script_successor else source.script_run_id
        new_run = replace(
            run,
            id=self.id_factory(),
            script_run_id=script_run_id,
            script_version_id=script_version_id,
            script_content_digest=script_successor.content_digest
            if script_successor
            else run.script_content_digest,
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            completed_at=now,
            version=1,
        )
        successor = replace(
            source,
            id=self.id_factory(),
            storyboard_run_id=new_run.id,
            script_run_id=script_run_id,
            script_version_id=script_version_id,
            version_number=source.version_number + 1,
            content=content,
            content_digest=_content_digest(content),
            created_at=now,
        )
        uow.storyboard_runs.add(new_run)
        uow.storyboard_versions.add(successor)
        uow.artifact_revision_links.add(
            self._link(
                context,
                project_id,
                ReviewArtifactType.STORYBOARD,
                source.id,
                successor.id,
                source.version_number,
                successor.version_number,
                request_id,
            )
        )
        return successor

    def _successor_shot_plan(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        source: ShotPlanVersion,
        content: dict[str, object],
        storyboard_successor: StoryboardVersion | None,
        script_successor: ScriptVersion | None,
        request_id: UUID,
    ) -> ShotPlanVersion:
        run = uow.shot_plan_runs.get(
            context.organization_id, context.workspace_id, project_id, source.shot_plan_run_id
        )
        if run is None or run.status is not CreativeRunStatus.COMPLETED:
            raise ResourceNotFound("shot plan version is not accessible")
        now = self.clock()
        storyboard_version_id = (
            storyboard_successor.id if storyboard_successor else source.storyboard_version_id
        )
        storyboard_run_id = (
            storyboard_successor.storyboard_run_id
            if storyboard_successor
            else source.storyboard_run_id
        )
        script_version_id = script_successor.id if script_successor else source.script_version_id
        script_run_id = script_successor.script_run_id if script_successor else source.script_run_id
        new_run = replace(
            run,
            id=self.id_factory(),
            storyboard_run_id=storyboard_run_id,
            storyboard_version_id=storyboard_version_id,
            script_run_id=script_run_id,
            script_version_id=script_version_id,
            storyboard_content_digest=storyboard_successor.content_digest
            if storyboard_successor
            else run.storyboard_content_digest,
            created_by_actor_subject=context.actor_subject,
            created_at=now,
            completed_at=now,
            version=1,
        )
        successor = replace(
            source,
            id=self.id_factory(),
            shot_plan_run_id=new_run.id,
            storyboard_run_id=storyboard_run_id,
            storyboard_version_id=storyboard_version_id,
            script_run_id=script_run_id,
            script_version_id=script_version_id,
            version_number=source.version_number + 1,
            content=content,
            content_digest=_content_digest(content),
            created_at=now,
        )
        uow.shot_plan_runs.add(new_run)
        uow.shot_plan_versions.add(successor)
        uow.artifact_revision_links.add(
            self._link(
                context,
                project_id,
                ReviewArtifactType.SHOT_PLAN,
                source.id,
                successor.id,
                source.version_number,
                successor.version_number,
                request_id,
            )
        )
        return successor

    def _link(
        self,
        context: TenantContext,
        project_id: UUID,
        artifact_type: ReviewArtifactType,
        predecessor: UUID,
        successor: UUID,
        predecessor_number: int,
        successor_number: int,
        request_id: UUID,
    ) -> ArtifactRevisionLink:
        return ArtifactRevisionLink(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            project_id,
            artifact_type,
            predecessor,
            successor,
            predecessor_number,
            successor_number,
            request_id,
            self.clock(),
        )

    def _load_review_artifacts(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        artifact_type: ReviewArtifactType,
        script_id: UUID | None,
        storyboard_id: UUID | None,
        shot_id: UUID | None,
    ) -> tuple[ScriptVersion | None, StoryboardVersion | None, ShotPlanVersion | None]:
        if artifact_type is ReviewArtifactType.SCRIPT:
            return self._require_script(uow, context, project_id, script_id), None, None
        if artifact_type is ReviewArtifactType.STORYBOARD:
            return None, self._require_storyboard(uow, context, project_id, storyboard_id), None
        if artifact_type is ReviewArtifactType.SHOT_PLAN:
            return None, None, self._require_shot_plan(uow, context, project_id, shot_id)
        return self._load_bundle(uow, context, project_id, script_id, storyboard_id, shot_id)

    def _load_bundle(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        script_id: UUID | None,
        storyboard_id: UUID | None,
        shot_id: UUID | None,
    ) -> tuple[ScriptVersion, StoryboardVersion, ShotPlanVersion]:
        script = self._require_script(uow, context, project_id, script_id)
        storyboard = self._require_storyboard(uow, context, project_id, storyboard_id)
        shot = self._require_shot_plan(uow, context, project_id, shot_id)
        self._validate_bundle(script, storyboard, shot, None)
        return script, storyboard, shot

    def _validate_bundle(
        self,
        script: ScriptVersion,
        storyboard: StoryboardVersion,
        shot: ShotPlanVersion,
        review: PlanningReview | None,
    ) -> None:
        if (
            storyboard.script_version_id != script.id
            or shot.storyboard_version_id != storyboard.id
            or shot.script_version_id != script.id
        ):
            raise ResourceNotFound("planning lineage is not accessible")
        if (
            _content_digest(script.content) != script.content_digest
            or _content_digest(storyboard.content) != storyboard.content_digest
            or _content_digest(shot.content) != shot.content_digest
        ):
            raise ResourceConflict("planning content digest changed")
        if review is not None and (
            review.outcome is not PlanningReviewOutcome.APPROVED
            or review.artifact_type is not ReviewArtifactType.PLANNING_BUNDLE
            or review.script_version_id != script.id
            or review.storyboard_version_id != storyboard.id
            or review.shot_plan_version_id != shot.id
        ):
            raise ResourceConflict("an exact approved planning bundle review is required")

    def _manifest(
        self,
        context: TenantContext,
        project_id: UUID,
        script: ScriptVersion,
        storyboard: StoryboardVersion,
        shot: ShotPlanVersion,
        review: PlanningReview,
        version_id: UUID,
    ) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "project": {
                "project_id": str(project_id),
                "organization_id": str(context.organization_id),
                "workspace_id": str(context.workspace_id),
            },
            "lineage": {
                "script_version_id": str(script.id),
                "storyboard_version_id": str(storyboard.id),
                "shot_plan_version_id": str(shot.id),
                "script_content_digest": script.content_digest,
                "storyboard_content_digest": storyboard.content_digest,
                "shot_plan_content_digest": shot.content_digest,
            },
            "artifacts": {
                "script": {
                    "schema_version": script.schema_version,
                    "duration": script.content.get("target_duration_seconds"),
                },
                "storyboard": {
                    "schema_version": storyboard.schema_version,
                    "scene_count": storyboard.scene_count,
                    "duration": storyboard.total_duration_seconds,
                },
                "shot_plan": {
                    "schema_version": shot.schema_version,
                    "scene_count": shot.scene_count,
                    "shot_count": shot.shot_count,
                    "duration": shot.total_duration_seconds,
                },
            },
            "review": {
                "review_id": str(review.id),
                "outcome": review.outcome.value,
                "review_round": review.review_round,
            },
            "summary": {"generation": "immutable structured planning artifacts"},
            "exports": sorted(EXPORT_FORMATS - {"delivery-package.zip"}),
            "package_version_id": str(version_id),
        }

    def _export_bytes(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        version: DeliveryPackageVersion,
        export_format: str,
    ) -> bytes:
        script = self._require_script(uow, context, project_id, version.script_version_id)
        storyboard = self._require_storyboard(
            uow, context, project_id, version.storyboard_version_id
        )
        shot = self._require_shot_plan(uow, context, project_id, version.shot_plan_version_id)
        self._validate_bundle(script, storyboard, shot, None)
        contents = self._export_contents(version, script, storyboard, shot)
        if export_format == "delivery-package.zip":
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for filename in sorted(contents):
                    info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o600 << 16
                    archive.writestr(info, contents[filename])
            payload = output.getvalue()
        else:
            payload = contents[export_format]
        if not payload or len(payload) > MAX_EXPORT_BYTES:
            raise InvalidRequest("export exceeds the allowed size", code="export_too_large")
        return payload

    def _export_contents(
        self,
        version: DeliveryPackageVersion,
        script: ScriptVersion,
        storyboard: StoryboardVersion,
        shot: ShotPlanVersion,
    ) -> dict[str, bytes]:
        def encoder(value: object) -> bytes:
            return json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()

        rows = shot.content.get("shots", [])
        csv_output = io.StringIO(newline="")
        if isinstance(rows, list):
            writer = csv.DictWriter(
                csv_output,
                fieldnames=[
                    "shot_id",
                    "shot_number",
                    "storyboard_scene_number",
                    "source_script_scene_number",
                    "estimated_duration_seconds",
                ],
                extrasaction="ignore",
                lineterminator="\n",
            )
            writer.writeheader()
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow(row)
        return {
            "manifest.json": encoder(version.manifest),
            "script.json": encoder(script.content),
            "storyboard.json": encoder(storyboard.content),
            "shot-plan.json": encoder(shot.content),
            "shot-plan.csv": csv_output.getvalue().encode(),
            "README.txt": (
                b"AI Video Preproduction planning package\n\n"
                b"This package contains immutable structured planning data only.\n"
            ),
        }

    def _stage(self, payload: bytes) -> str:
        async def chunks() -> AsyncIterator[bytes]:
            yield payload

        try:
            staged = asyncio.run(self.storage.stage(chunks(), max_bytes=MAX_EXPORT_BYTES))
            return staged.storage_key
        except (StorageError, RuntimeError) as error:
            raise StorageUnavailable("delivery export storage is unavailable") from error

    def _delete_quietly(self, key: str) -> None:
        with suppress(StorageError):
            self.storage.delete(key)

    def _new_revision_request(
        self,
        context: TenantContext,
        project_id: UUID,
        review: PlanningReview,
        changes: dict[str, object],
        artifacts: tuple[ScriptVersion | None, StoryboardVersion | None, ShotPlanVersion | None],
    ) -> PlanningRevisionRequest:
        script, storyboard, shot = artifacts
        digest = _digest(
            {
                "review_id": str(review.id),
                "artifact_type": review.artifact_type.value,
                "source_ids": [str(value.id) if value else None for value in artifacts],
                "requested_changes": changes,
            }
        )
        return PlanningRevisionRequest(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            project_id,
            review.id,
            review.artifact_type,
            script.id if script else None,
            storyboard.id if storyboard else None,
            shot.id if shot else None,
            changes,
            digest,
            RevisionRequestStatus.OPEN,
            context.actor_subject,
            self.clock(),
            None,
            None,
            None,
            None,
            1,
        )

    def _resolve_operation(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        operation: DeliveryOperationType,
        key: str,
        digest: str,
    ) -> DeliveryOperation | None:
        existing = uow.delivery_operations.get_by_key(
            context.organization_id, context.workspace_id, project_id, operation, key
        )
        if existing is None:
            return None
        if existing.request_digest != digest:
            raise ResourceConflict(
                "idempotency key was used for a different request", code="idempotency_conflict"
            )
        if existing.status is DeliveryOperationStatus.RESERVED:
            raise ResourceConflict("delivery operation is not complete")
        return existing

    def _reserve(
        self,
        context: TenantContext,
        project_id: UUID,
        operation: DeliveryOperationType,
        key: str,
        digest: str,
    ) -> DeliveryOperation:
        return DeliveryOperation(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            project_id,
            operation,
            key,
            digest,
            DeliveryOperationStatus.RESERVED,
            None,
            None,
            None,
            None,
            None,
            context.actor_subject,
            self.clock(),
            None,
            context.correlation_id,
            1,
        )

    def _require_mutation(self, uow: UnitOfWork, context: TenantContext, project_id: UUID) -> None:
        self._briefs._require_project_access(uow, context, project_id, READ_ROLES, mutable=True)
        membership = uow.memberships.find_effective(
            context.organization_id, context.workspace_id, context.actor_subject
        )
        if membership is None or membership.role not in MUTATION_ROLES:
            raise PermissionDenied("review and delivery mutation is not permitted")

    def _require_read(self, uow: UnitOfWork, context: TenantContext, project_id: UUID) -> None:
        self._briefs._require_project_access(uow, context, project_id, READ_ROLES)

    def _require_review(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, review_id: UUID | None
    ) -> PlanningReview:
        if review_id is None:
            raise ResourceConflict("review outcome is unavailable")
        value = uow.planning_reviews.get(
            context.organization_id, context.workspace_id, project_id, review_id
        )
        if value is None:
            raise ResourceNotFound("planning review is not accessible")
        return value

    def _require_revision(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, request_id: UUID | None
    ) -> PlanningRevisionRequest:
        if request_id is None:
            raise ResourceConflict("revision request outcome is unavailable")
        value = uow.planning_revision_requests.get(
            context.organization_id, context.workspace_id, project_id, request_id
        )
        if value is None:
            raise ResourceNotFound("revision request is not accessible")
        return value

    def _require_package(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, package_id: UUID | None
    ) -> DeliveryPackage:
        if package_id is None:
            raise ResourceConflict("delivery package outcome is unavailable")
        value = uow.delivery_packages.get(
            context.organization_id, context.workspace_id, project_id, package_id
        )
        if value is None:
            raise ResourceNotFound("delivery package is not accessible")
        return value

    def _require_package_version(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, version_id: UUID | None
    ) -> DeliveryPackageVersion:
        if version_id is None:
            raise ResourceConflict("delivery package outcome is unavailable")
        value = uow.delivery_package_versions.get(
            context.organization_id, context.workspace_id, project_id, version_id
        )
        if value is None:
            raise ResourceNotFound("delivery package is not accessible")
        return value

    def _require_export(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, export_id: UUID | None
    ) -> DeliveryExportFile:
        if export_id is None:
            raise ResourceConflict("export outcome is unavailable")
        value = uow.delivery_export_files.get(
            context.organization_id, context.workspace_id, project_id, export_id
        )
        if value is None:
            raise ResourceConflict("export outcome is unavailable")
        return value

    def _require_script(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, version_id: UUID | None
    ) -> ScriptVersion:
        if version_id is None:
            raise ResourceNotFound("script version is not accessible")
        value = uow.script_versions.get(
            context.organization_id, context.workspace_id, project_id, version_id
        )
        if value is None:
            raise ResourceNotFound("script version is not accessible")
        return value

    def _require_storyboard(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, version_id: UUID | None
    ) -> StoryboardVersion:
        if version_id is None:
            raise ResourceNotFound("storyboard version is not accessible")
        value = uow.storyboard_versions.get(
            context.organization_id, context.workspace_id, project_id, version_id
        )
        if value is None:
            raise ResourceNotFound("storyboard version is not accessible")
        return value

    def _require_shot_plan(
        self, uow: UnitOfWork, context: TenantContext, project_id: UUID, version_id: UUID | None
    ) -> ShotPlanVersion:
        if version_id is None:
            raise ResourceNotFound("shot plan version is not accessible")
        value = uow.shot_plan_versions.get(
            context.organization_id, context.workspace_id, project_id, version_id
        )
        if value is None:
            raise ResourceNotFound("shot plan version is not accessible")
        return value

    def _validate_script(self, content: dict[str, object]) -> None:
        try:
            validate_script(content)
        except (ValidationError, ValueError) as error:
            raise InvalidRequest("script revision is invalid", code="schema_invalid") from error

    def _validate_storyboard(self, content: dict[str, object], script: ScriptVersion) -> None:
        try:
            validate_storyboard(content)
            from services.api.app.application.visual_planning_services import (
                VisualPlanningApplicationService,
            )

            VisualPlanningApplicationService._validate_storyboard_content(content, script)
        except ValidationError as error:
            raise InvalidRequest(
                "storyboard revision is schema invalid", code="schema_invalid"
            ) from error
        except ValueError as error:
            raise InvalidRequest(
                "storyboard revision is semantically invalid", code="semantic_invalid"
            ) from error

    def _validate_shot_plan(
        self, content: dict[str, object], storyboard: StoryboardVersion, script: ScriptVersion
    ) -> None:
        try:
            validate_shot_plan(content)
            from services.api.app.application.visual_planning_services import (
                VisualPlanningApplicationService,
            )

            VisualPlanningApplicationService._validate_shot_plan_content(
                content, storyboard, script
            )
        except ValidationError as error:
            raise InvalidRequest(
                "shot plan revision is schema invalid", code="schema_invalid"
            ) from error
        except ValueError as error:
            raise InvalidRequest(
                "shot plan revision is semantically invalid", code="semantic_invalid"
            ) from error

    def _audit(
        self, context: TenantContext, aggregate_id: UUID, action: str, payload: dict[str, object]
    ) -> AuditEvent:
        return AuditEvent(
            self.id_factory(),
            context.organization_id,
            context.workspace_id,
            context.actor_subject,
            "review_revision_delivery",
            aggregate_id,
            action,
            payload,
            self.clock(),
            context.correlation_id,
            None,
        )

    def _validate_review_input(
        self,
        artifact_type: ReviewArtifactType,
        outcome: PlanningReviewOutcome,
        summary: str,
        requested_changes: dict[str, object],
        script_version_id: UUID | None,
        storyboard_version_id: UUID | None,
        shot_plan_version_id: UUID | None,
    ) -> None:
        if not 1 <= len(summary) <= 1000:
            raise InvalidRequest("review summary must be between 1 and 1000 characters")
        if not isinstance(requested_changes, dict):
            raise InvalidRequest("requested_changes must be an object")
        if outcome is not PlanningReviewOutcome.REVISION_REQUESTED and requested_changes:
            raise InvalidRequest("requested_changes require a revision request")
        identifiers = (script_version_id, storyboard_version_id, shot_plan_version_id)
        expected_count = 3 if artifact_type is ReviewArtifactType.PLANNING_BUNDLE else 1
        if sum(identifier is not None for identifier in identifiers) != expected_count:
            raise InvalidRequest("artifact identifiers do not match artifact type")
        if artifact_type is ReviewArtifactType.SCRIPT and script_version_id is None:
            raise InvalidRequest("script review requires a script version")
        if artifact_type is ReviewArtifactType.STORYBOARD and storyboard_version_id is None:
            raise InvalidRequest("storyboard review requires a storyboard version")
        if artifact_type is ReviewArtifactType.SHOT_PLAN and shot_plan_version_id is None:
            raise InvalidRequest("shot plan review requires a shot plan version")


def _scope(context: TenantContext, project_id: UUID) -> dict[str, str]:
    return {
        "organization_id": str(context.organization_id),
        "workspace_id": str(context.workspace_id),
        "project_id": str(project_id),
    }


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _content_digest(value: dict[str, object]) -> str:
    return _digest(value)


def _artifact_digests(
    artifacts: tuple[ScriptVersion | None, StoryboardVersion | None, ShotPlanVersion | None],
) -> list[str | None]:
    return [value.content_digest if value else None for value in artifacts]


def _mode_set(artifact_type: ReviewArtifactType) -> frozenset[str]:
    if artifact_type is ReviewArtifactType.SCRIPT:
        return SCRIPT_REVISION_MODES
    if artifact_type is ReviewArtifactType.STORYBOARD:
        return STORYBOARD_REVISION_MODES
    return SHOT_PLAN_REVISION_MODES


def _revision_content(
    source: dict[str, object], changes: dict[str, object], mode: str, artifact_type: str
) -> dict[str, object]:
    if mode == "refusal":
        raise InvalidRequest("revision provider refused the request", code="refusal")
    if mode == "timeout":
        raise InvalidRequest("revision provider timed out", code="timeout")
    if mode == "provider_error":
        raise InvalidRequest("revision provider failed", code="provider_error")
    if mode == "malformed":
        raise InvalidRequest("revision provider output is malformed", code="malformed_output")
    result = deepcopy(source)
    if mode == "schema_invalid":
        return {"schema_version": "invalid"}
    if artifact_type == "script":
        scenes = result.get("scenes")
        first_scene = scenes[0] if isinstance(scenes, list) and scenes else None
        if isinstance(first_scene, dict):
            first_scene["action"] = f"{first_scene.get('action', 'Revised')} (revision)"
            if mode == "duration_invalid":
                first_scene["estimated_duration_seconds"] = 999
    elif artifact_type == "storyboard":
        scenes = result.get("scenes")
        if isinstance(scenes, list) and scenes and isinstance(scenes[0], dict):
            scenes[0]["visual_summary"] = f"{scenes[0].get('visual_summary', 'Revised')} (revision)"
            if mode == "scene_mismatch":
                scenes[0]["source_script_scene_number"] = 999
            if mode == "duration_invalid":
                scenes[0]["estimated_duration_seconds"] = 999
    else:
        shots = result.get("shots")
        if isinstance(shots, list) and shots and isinstance(shots[0], dict):
            shots[0]["generation_prompt"] = (
                f"{shots[0].get('generation_prompt', 'Revised')} (revision)"
            )
            if mode == "shot_order_invalid":
                shots[0]["shot_number"] = 2
            if mode == "scene_coverage_invalid":
                result["shots"] = []
            if mode == "continuity_invalid":
                shots[0]["continuity_requirements"] = ["future shot 999 must match"]
            if mode == "duration_invalid":
                shots[0]["estimated_duration_seconds"] = 999
    return result


def _filename(export_format: str) -> str:
    return export_format.replace("/", "_")
