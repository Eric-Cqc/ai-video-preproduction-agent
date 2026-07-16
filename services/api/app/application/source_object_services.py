import hashlib
import json
import logging
from collections.abc import AsyncIterable, Callable, Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import (
    InvalidRequest,
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
from services.api.app.application.storage import (
    StagedObject,
    StorageError,
    StoragePort,
    StorageValidationError,
)
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    AuditEvent,
    MembershipRole,
    OrganizationStatus,
    ProjectStatus,
    SourceAssetStatus,
    SourceAssetVersion,
    SourceObject,
    SourceObjectCleanupRequirement,
    SourceObjectState,
    SourceObjectUpload,
    SourceObjectUploadStatus,
    WorkspaceStatus,
)

UPLOAD_OPERATION = "upload_source_object"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceObjectUploadResult:
    source_object: SourceObject
    upload: SourceObjectUpload
    replayed: bool


class SourceObjectApplicationService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        storage: StoragePort,
        *,
        max_upload_bytes: int,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.storage = storage
        self.max_upload_bytes = max_upload_bytes
        self.clock = clock
        self.id_factory = id_factory

    async def upload(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        *,
        idempotency_key: str,
        chunks: AsyncIterable[bytes],
    ) -> SourceObjectUploadResult:
        declared = self._authorize_target(
            context, project_id, source_asset_id, source_asset_version_id, mutation=True
        )
        try:
            staged = await self.storage.stage(chunks, max_bytes=self.max_upload_bytes)
        except StorageValidationError as error:
            raise InvalidRequest(str(error)) from error
        except StorageError as error:
            raise StorageUnavailable("Object storage is unavailable") from error

        digest = self._digest(source_asset_id, source_asset_version_id, staged)
        final_key: str | None = None
        finalized = False
        try:
            with self.uow_factory() as uow:
                self._require_access(uow, context, project_id, MUTATION_ROLES)
                asset = uow.source_assets.get(
                    context.organization_id, context.workspace_id, project_id, source_asset_id
                )
                version = uow.source_asset_versions.get(
                    context.organization_id,
                    context.workspace_id,
                    project_id,
                    source_asset_id,
                    source_asset_version_id,
                )
                if asset is None or version is None:
                    raise ResourceNotFound("source asset version is not accessible")
                reservation = SourceObjectUpload(
                    id=self.id_factory(),
                    organization_id=context.organization_id,
                    workspace_id=context.workspace_id,
                    project_id=project_id,
                    source_asset_id=source_asset_id,
                    source_asset_version_id=source_asset_version_id,
                    source_object_id=None,
                    operation=UPLOAD_OPERATION,
                    idempotency_key=idempotency_key,
                    request_digest=digest,
                    status=SourceObjectUploadStatus.RESERVED,
                    submitted_by_actor_subject=context.actor_subject,
                    submitted_at=self.clock(),
                    completed_at=None,
                    correlation_id=context.correlation_id,
                    version=1,
                )
                won = uow.source_object_uploads.reserve(reservation)
                if won is None:
                    existing = uow.source_object_uploads.get_scoped_by_key(
                        context.organization_id,
                        context.workspace_id,
                        project_id,
                        UPLOAD_OPERATION,
                        idempotency_key,
                    )
                    if existing is None:
                        raise ResourceConflict("upload reservation could not be resolved")
                    if existing.request_digest != digest:
                        raise ResourceConflict(
                            "idempotency key was used for different uploaded bytes",
                            code="idempotency_conflict",
                        )
                    if (
                        existing.status is not SourceObjectUploadStatus.ACCEPTED
                        or existing.source_object_id is None
                    ):
                        raise ResourceConflict("upload reservation is not complete")
                    source_object = uow.source_objects.get_for_version(
                        context.organization_id,
                        context.workspace_id,
                        project_id,
                        source_asset_id,
                        source_asset_version_id,
                    )
                    if source_object is None or source_object.id != existing.source_object_id:
                        raise ResourceConflict("accepted upload outcome is unavailable")
                    try:
                        self.storage.delete(staged.storage_key)
                    except StorageError:
                        uow.source_object_cleanup_requirements.add(
                            self._cleanup(
                                context, project_id, staged.storage_key, "replay_cleanup_failure"
                            )
                        )
                    result = SourceObjectUploadResult(source_object, existing, True)
                else:
                    if asset.status is not SourceAssetStatus.ACTIVE:
                        raise ResourceConflict("archived source assets cannot receive uploads")
                    if (
                        staged.observed_byte_size != declared.byte_size
                        or staged.observed_checksum_value != declared.checksum_value
                    ):
                        raise InvalidRequest(
                            "uploaded bytes do not match declared source asset metadata"
                        )
                    if (
                        uow.source_objects.get_for_version(
                            context.organization_id,
                            context.workspace_id,
                            project_id,
                            source_asset_id,
                            source_asset_version_id,
                        )
                        is not None
                    ):
                        raise ResourceConflict("source asset version already has uploaded bytes")
                    final_key = self.storage.new_final_key()
                    self.storage.finalize(staged.storage_key, final_key)
                    finalized = True
                    now = self.clock()
                    source_object = uow.source_objects.add(
                        SourceObject(
                            id=self.id_factory(),
                            organization_id=context.organization_id,
                            workspace_id=context.workspace_id,
                            project_id=project_id,
                            source_asset_id=source_asset_id,
                            source_asset_version_id=source_asset_version_id,
                            storage_adapter=self.storage.adapter_name,
                            storage_key=final_key,
                            state=SourceObjectState.AVAILABLE,
                            observed_byte_size=staged.observed_byte_size,
                            observed_checksum_algorithm="sha256",
                            observed_checksum_value=staged.observed_checksum_value,
                            created_by_actor_subject=context.actor_subject,
                            created_at=now,
                            version=1,
                        )
                    )
                    accepted = uow.source_object_uploads.finalize_accepted(
                        won,
                        source_object_id=source_object.id,
                        completed_at=now,
                        expected_version=1,
                    )
                    uow.audit_events.append(
                        AuditEvent(
                            id=self.id_factory(),
                            organization_id=context.organization_id,
                            workspace_id=context.workspace_id,
                            actor_subject=context.actor_subject,
                            aggregate_type="source_object",
                            aggregate_id=source_object.id,
                            action="source_object.uploaded",
                            payload={
                                "source_object_id": str(source_object.id),
                                "source_asset_id": str(source_asset_id),
                                "source_asset_version_id": str(source_asset_version_id),
                                "observed_byte_size": staged.observed_byte_size,
                                "storage_adapter": self.storage.adapter_name,
                            },
                            occurred_at=now,
                            correlation_id=context.correlation_id,
                        )
                    )
                    result = SourceObjectUploadResult(source_object, accepted, False)
            return result
        except StorageError as error:
            cleanup_key = final_key if finalized and final_key is not None else staged.storage_key
            self._compensate(context, project_id, cleanup_key)
            raise StorageUnavailable("Object storage is unavailable") from error
        except BaseException:
            cleanup_key = final_key if finalized and final_key is not None else staged.storage_key
            self._compensate(context, project_id, cleanup_key)
            raise

    def get(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
    ) -> SourceObject:
        with self.uow_factory() as uow:
            self._require_access(uow, context, project_id, READ_ROLES)
            if (
                uow.source_assets.get(
                    context.organization_id, context.workspace_id, project_id, source_asset_id
                )
                is None
            ):
                raise ResourceNotFound("source object is not accessible")
            source_object = uow.source_objects.get_for_version(
                context.organization_id,
                context.workspace_id,
                project_id,
                source_asset_id,
                source_asset_version_id,
            )
            if source_object is None:
                raise ResourceNotFound("source object is not accessible")
            return source_object

    def read(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
    ) -> tuple[SourceObject, Iterator[bytes]]:
        source_object = self.get(context, project_id, source_asset_id, source_asset_version_id)
        try:
            return source_object, self.storage.read(source_object.storage_key)
        except StorageError as error:
            raise StorageUnavailable("Object storage is unavailable") from error

    def _authorize_target(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        version_id: UUID,
        *,
        mutation: bool,
    ) -> SourceAssetVersion:
        with self.uow_factory() as uow:
            self._require_access(
                uow, context, project_id, MUTATION_ROLES if mutation else READ_ROLES
            )
            asset = uow.source_assets.get(
                context.organization_id, context.workspace_id, project_id, source_asset_id
            )
            version = uow.source_asset_versions.get(
                context.organization_id,
                context.workspace_id,
                project_id,
                source_asset_id,
                version_id,
            )
            if asset is None or version is None:
                raise ResourceNotFound("source asset version is not accessible")
            return version

    @staticmethod
    def _require_access(
        uow: UnitOfWork, context: TenantContext, project_id: UUID, roles: frozenset[MembershipRole]
    ) -> None:
        organization = uow.organizations.get(context.organization_id)
        workspace = uow.workspaces.get(context.organization_id, context.workspace_id)
        membership = uow.memberships.find_effective(
            context.organization_id, context.workspace_id, context.actor_subject
        )
        project = uow.projects.get(context.organization_id, context.workspace_id, project_id)
        if (
            organization is None
            or organization.status is not OrganizationStatus.ACTIVE
            or workspace is None
            or workspace.status is not WorkspaceStatus.ACTIVE
            or membership is None
            or membership.role not in roles
            or project is None
        ):
            raise ResourceNotFound("project is not accessible")
        if project.status is ProjectStatus.ARCHIVED:
            raise ResourceConflict("archived projects cannot be changed", code="project_archived")

    @staticmethod
    def _digest(asset_id: UUID, version_id: UUID, staged: StagedObject) -> str:
        encoded = json.dumps(
            {
                "operation": UPLOAD_OPERATION,
                "source_asset_id": str(asset_id),
                "source_asset_version_id": str(version_id),
                "observed_byte_size": staged.observed_byte_size,
                "observed_checksum_value": staged.observed_checksum_value,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _cleanup(
        self, context: TenantContext, project_id: UUID, key: str, reason: str
    ) -> SourceObjectCleanupRequirement:
        return SourceObjectCleanupRequirement(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            storage_adapter=self.storage.adapter_name,
            storage_key=key,
            reason_code=reason,
            created_at=self.clock(),
        )

    def _compensate(self, context: TenantContext, project_id: UUID, key: str) -> None:
        self._delete_or_record(context, project_id, key, "database_failure")

    def _delete_or_record(
        self, context: TenantContext, project_id: UUID, key: str, reason: str
    ) -> None:
        try:
            self.storage.delete(key)
        except StorageError:
            try:
                with self.uow_factory() as uow:
                    uow.source_object_cleanup_requirements.add(
                        self._cleanup(context, project_id, key, reason)
                    )
            except Exception:
                logger.error(
                    "failed to persist bounded storage cleanup requirement",
                    extra={
                        "event": "source_object.cleanup_record_failed",
                        "correlation_id": context.correlation_id,
                    },
                )
