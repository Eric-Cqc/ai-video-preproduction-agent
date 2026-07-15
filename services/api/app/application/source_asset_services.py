import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import InvalidRequest, ResourceConflict, ResourceNotFound
from services.api.app.application.services import (
    ADMIN_ROLES,
    MUTATION_ROLES,
    READ_ROLES,
    Clock,
    IdFactory,
    utc_now,
)
from services.api.app.application.uow import UnitOfWork
from services.api.app.domain import (
    AuditEvent,
    Membership,
    MembershipRole,
    OrganizationStatus,
    ProjectStatus,
    SourceAsset,
    SourceAssetMediaType,
    SourceAssetOperation,
    SourceAssetOperationStatus,
    SourceAssetOperationType,
    SourceAssetSourceType,
    SourceAssetStatus,
    SourceAssetVersion,
    WorkspaceStatus,
)


@dataclass(frozen=True, slots=True)
class SourceAssetResult:
    operation: SourceAssetOperation
    asset: SourceAsset
    version: SourceAssetVersion
    duplicate_count: int
    replayed: bool


class SourceAssetApplicationService:
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

    def create_asset(
        self,
        context: TenantContext,
        project_id: UUID,
        *,
        idempotency_key: str,
        display_name: str,
        original_filename: str,
        media_type: str,
        byte_size: int,
        checksum_algorithm: str,
        checksum_value: str,
        source_type: str,
        source_reference: str | None,
        external_record_id: str | None,
        declared_created_at: datetime | None,
    ) -> SourceAssetResult:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, MUTATION_ROLES)
            digest = self._digest(
                SourceAssetOperationType.CREATE_SOURCE_ASSET,
                {
                    "display_name": display_name,
                    "original_filename": original_filename,
                    "media_type": media_type,
                    "byte_size": byte_size,
                    "checksum_algorithm": checksum_algorithm,
                    "checksum_value": checksum_value,
                    "source_type": source_type,
                    "source_reference": source_reference,
                    "external_record_id": external_record_id,
                    "declared_created_at": self._datetime_value(declared_created_at),
                },
            )
            replay = self._reserve_or_replay(
                uow,
                context,
                project_id,
                SourceAssetOperationType.CREATE_SOURCE_ASSET,
                idempotency_key,
                digest,
                now,
            )
            if replay is not None:
                return replay

            operation = self._require_reservation(
                uow,
                context,
                project_id,
                SourceAssetOperationType.CREATE_SOURCE_ASSET,
                idempotency_key,
            )
            asset_id, version_id = self.id_factory(), self.id_factory()
            asset = SourceAsset.create(
                id=asset_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                display_name=display_name,
                initial_version_id=version_id,
                created_by_actor_subject=context.actor_subject,
                now=now,
            )
            version = SourceAssetVersion.create(
                id=version_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                source_asset_id=asset_id,
                version_number=1,
                original_filename=original_filename,
                media_type=media_type,
                byte_size=byte_size,
                checksum_algorithm=checksum_algorithm,
                checksum_value=checksum_value,
                source_type=source_type,
                source_reference=source_reference,
                external_record_id=external_record_id,
                declared_created_at=declared_created_at,
                created_by_actor_subject=context.actor_subject,
                created_at=now,
                supersedes_version_id=None,
            )
            duplicate_count = self._duplicate_count(uow, context, project_id, version)
            saved_asset = uow.source_assets.add(asset)
            saved_version = uow.source_asset_versions.add(version)
            accepted = uow.source_asset_operations.finalize_accepted(
                operation,
                source_asset_id=asset_id,
                source_asset_version_id=version_id,
                completed_at=now,
                expected_version=1,
            )
            uow.audit_events.append(
                self._audit(
                    context,
                    saved_asset,
                    saved_version,
                    "source_asset.created",
                    duplicate_count,
                    now,
                )
            )
            return SourceAssetResult(accepted, saved_asset, saved_version, duplicate_count, False)

    def create_version(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        *,
        idempotency_key: str,
        expected_asset_version: int,
        expected_current_version_id: UUID,
        source_version_id: UUID,
        original_filename: str,
        media_type: str,
        byte_size: int,
        checksum_algorithm: str,
        checksum_value: str,
        source_type: str,
        source_reference: str | None,
        external_record_id: str | None,
        declared_created_at: datetime | None,
    ) -> SourceAssetResult:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, MUTATION_ROLES)
            digest = self._digest(
                SourceAssetOperationType.CREATE_SOURCE_ASSET_VERSION,
                {
                    "source_asset_id": str(source_asset_id),
                    "expected_asset_version": expected_asset_version,
                    "expected_current_version_id": str(expected_current_version_id),
                    "source_version_id": str(source_version_id),
                    "original_filename": original_filename,
                    "media_type": media_type,
                    "byte_size": byte_size,
                    "checksum_algorithm": checksum_algorithm,
                    "checksum_value": checksum_value,
                    "source_type": source_type,
                    "source_reference": source_reference,
                    "external_record_id": external_record_id,
                    "declared_created_at": self._datetime_value(declared_created_at),
                },
            )
            replay = self._reserve_or_replay(
                uow,
                context,
                project_id,
                SourceAssetOperationType.CREATE_SOURCE_ASSET_VERSION,
                idempotency_key,
                digest,
                now,
            )
            if replay is not None:
                return replay

            current = self._require_asset(uow, context, project_id, source_asset_id)
            if source_version_id != current.current_version_id:
                raise ResourceConflict(
                    "source asset version is no longer current", code="version_conflict"
                )
            predecessor = self._require_version(
                uow, context, project_id, current.id, source_version_id
            )
            operation = self._require_reservation(
                uow,
                context,
                project_id,
                SourceAssetOperationType.CREATE_SOURCE_ASSET_VERSION,
                idempotency_key,
            )
            new_version_id = self.id_factory()
            next_asset = current.new_version(
                expected_version=expected_asset_version, new_version_id=new_version_id, now=now
            )
            version = SourceAssetVersion.create(
                id=new_version_id,
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                source_asset_id=source_asset_id,
                version_number=current.latest_version_number + 1,
                original_filename=original_filename,
                media_type=media_type,
                byte_size=byte_size,
                checksum_algorithm=checksum_algorithm,
                checksum_value=checksum_value,
                source_type=source_type,
                source_reference=source_reference,
                external_record_id=external_record_id,
                declared_created_at=declared_created_at,
                created_by_actor_subject=context.actor_subject,
                created_at=now,
                supersedes_version_id=predecessor.id,
            )
            duplicate_count = self._duplicate_count(
                uow, context, project_id, version, exclude_source_asset_id=source_asset_id
            )
            saved_version = uow.source_asset_versions.add(version)
            saved_asset = uow.source_assets.compare_and_move_pointer(
                next_asset,
                expected_version=expected_asset_version,
                expected_current_version_id=expected_current_version_id,
            )
            accepted = uow.source_asset_operations.finalize_accepted(
                operation,
                source_asset_id=source_asset_id,
                source_asset_version_id=new_version_id,
                completed_at=now,
                expected_version=1,
            )
            uow.audit_events.append(
                self._audit(
                    context,
                    saved_asset,
                    saved_version,
                    "source_asset.version_created",
                    duplicate_count,
                    now,
                )
            )
            return SourceAssetResult(accepted, saved_asset, saved_version, duplicate_count, False)

    def archive_asset(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        *,
        idempotency_key: str,
        expected_asset_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAssetResult:
        now = self.clock()
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, ADMIN_ROLES)
            digest = self._digest(
                SourceAssetOperationType.ARCHIVE_SOURCE_ASSET,
                {
                    "source_asset_id": str(source_asset_id),
                    "expected_asset_version": expected_asset_version,
                    "expected_current_version_id": str(expected_current_version_id),
                },
            )
            replay = self._reserve_or_replay(
                uow,
                context,
                project_id,
                SourceAssetOperationType.ARCHIVE_SOURCE_ASSET,
                idempotency_key,
                digest,
                now,
            )
            if replay is not None:
                return replay

            current = self._require_asset(uow, context, project_id, source_asset_id)
            current_version = self._require_version(
                uow, context, project_id, source_asset_id, current.current_version_id
            )
            operation = self._require_reservation(
                uow,
                context,
                project_id,
                SourceAssetOperationType.ARCHIVE_SOURCE_ASSET,
                idempotency_key,
            )
            archived = current.archive(expected_version=expected_asset_version, now=now)
            saved_asset = uow.source_assets.compare_and_archive(
                archived,
                expected_version=expected_asset_version,
                expected_current_version_id=expected_current_version_id,
            )
            accepted = uow.source_asset_operations.finalize_accepted(
                operation,
                source_asset_id=source_asset_id,
                source_asset_version_id=current_version.id,
                completed_at=now,
                expected_version=1,
            )
            uow.audit_events.append(
                self._audit(
                    context,
                    saved_asset,
                    current_version,
                    "source_asset.archived",
                    0,
                    now,
                )
            )
            return SourceAssetResult(accepted, saved_asset, current_version, 0, False)

    def get_asset(
        self, context: TenantContext, project_id: UUID, source_asset_id: UUID
    ) -> SourceAsset:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            return self._require_asset(uow, context, project_id, source_asset_id)

    def list_assets(
        self, context: TenantContext, project_id: UUID, *, limit: int, offset: int
    ) -> list[SourceAsset]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            return uow.source_assets.list(
                context.organization_id,
                context.workspace_id,
                project_id,
                limit=limit,
                offset=offset,
            )

    def get_version(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        version_id: UUID,
    ) -> SourceAssetVersion:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            self._require_asset(uow, context, project_id, source_asset_id)
            return self._require_version(uow, context, project_id, source_asset_id, version_id)

    def list_versions(
        self, context: TenantContext, project_id: UUID, source_asset_id: UUID
    ) -> list[SourceAssetVersion]:
        with self.uow_factory() as uow:
            self._require_project_access(uow, context, project_id, READ_ROLES)
            self._require_asset(uow, context, project_id, source_asset_id)
            return uow.source_asset_versions.list_for_asset(
                context.organization_id,
                context.workspace_id,
                project_id,
                source_asset_id,
            )

    def _reserve_or_replay(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        operation_type: SourceAssetOperationType,
        key: str,
        digest: str,
        now: datetime,
    ) -> SourceAssetResult | None:
        if not 1 <= len(key) <= 128:
            raise InvalidRequest("idempotency key is outside the allowed length")
        reservation = SourceAssetOperation(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            source_asset_id=None,
            source_asset_version_id=None,
            operation=operation_type,
            idempotency_key=key,
            request_digest=digest,
            status=SourceAssetOperationStatus.RESERVED,
            submitted_by_actor_subject=context.actor_subject,
            submitted_at=now,
            completed_at=None,
            correlation_id=context.correlation_id,
            version=1,
        )
        won = uow.source_asset_operations.reserve(reservation)
        if won is not None:
            return None
        existing = uow.source_asset_operations.get_scoped_by_key(
            context.organization_id, context.workspace_id, project_id, operation_type, key
        )
        if existing is None:
            raise ResourceConflict("source asset operation reservation could not be resolved")
        if existing.request_digest != digest:
            raise ResourceConflict(
                "idempotency key was used for a different source asset request",
                code="idempotency_conflict",
            )
        if existing.status is not SourceAssetOperationStatus.ACCEPTED:
            raise ResourceConflict("source asset operation reservation is not complete")
        return self._result(uow, context, existing, replayed=True)

    def _result(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        operation: SourceAssetOperation,
        *,
        replayed: bool,
    ) -> SourceAssetResult:
        if operation.source_asset_id is None or operation.source_asset_version_id is None:
            raise ResourceConflict("source asset operation does not have an accepted outcome")
        asset = self._require_asset(uow, context, operation.project_id, operation.source_asset_id)
        version = self._require_version(
            uow, context, operation.project_id, asset.id, operation.source_asset_version_id
        )
        return SourceAssetResult(operation, asset, version, 0, replayed)

    @staticmethod
    def _require_project_access(
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        allowed_roles: frozenset[MembershipRole],
    ) -> None:
        organization = uow.organizations.get(context.organization_id)
        workspace = uow.workspaces.get(context.organization_id, context.workspace_id)
        membership: Membership | None = uow.memberships.find_effective(
            context.organization_id, context.workspace_id, context.actor_subject
        )
        project = uow.projects.get(context.organization_id, context.workspace_id, project_id)
        if (
            organization is None
            or organization.status is not OrganizationStatus.ACTIVE
            or workspace is None
            or workspace.status is not WorkspaceStatus.ACTIVE
            or membership is None
            or membership.role not in allowed_roles
            or project is None
        ):
            raise ResourceNotFound("project is not accessible")
        if project.status is ProjectStatus.ARCHIVED:
            raise ResourceConflict("archived projects cannot be changed", code="project_archived")

    @staticmethod
    def _require_asset(
        uow: UnitOfWork, context: TenantContext, project_id: UUID, source_asset_id: UUID
    ) -> SourceAsset:
        asset = uow.source_assets.get(
            context.organization_id, context.workspace_id, project_id, source_asset_id
        )
        if asset is None:
            raise ResourceNotFound("source asset is not accessible")
        return asset

    @staticmethod
    def _require_version(
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        version_id: UUID,
    ) -> SourceAssetVersion:
        version = uow.source_asset_versions.get(
            context.organization_id,
            context.workspace_id,
            project_id,
            source_asset_id,
            version_id,
        )
        if version is None:
            raise ResourceNotFound("source asset version is not accessible")
        return version

    def _require_reservation(
        self,
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        operation_type: SourceAssetOperationType,
        key: str,
    ) -> SourceAssetOperation:
        operation = uow.source_asset_operations.get_scoped_by_key(
            context.organization_id, context.workspace_id, project_id, operation_type, key
        )
        if operation is None or operation.status is not SourceAssetOperationStatus.RESERVED:
            raise ResourceConflict("source asset operation reservation was lost")
        return operation

    @staticmethod
    def _duplicate_count(
        uow: UnitOfWork,
        context: TenantContext,
        project_id: UUID,
        version: SourceAssetVersion,
        *,
        exclude_source_asset_id: UUID | None = None,
    ) -> int:
        return uow.source_asset_versions.find_declared_duplicate_within_project(
            context.organization_id,
            context.workspace_id,
            project_id,
            checksum_algorithm=version.checksum_algorithm,
            checksum_value=version.checksum_value,
            byte_size=version.byte_size,
            media_type=version.media_type.value,
            exclude_source_asset_id=exclude_source_asset_id,
        )

    def _audit(
        self,
        context: TenantContext,
        asset: SourceAsset,
        version: SourceAssetVersion,
        action: str,
        duplicate_count: int,
        now: datetime,
    ) -> AuditEvent:
        return AuditEvent(
            id=self.id_factory(),
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            actor_subject=context.actor_subject,
            aggregate_type="source_asset",
            aggregate_id=asset.id,
            action=action,
            payload={
                "source_asset_id": str(asset.id),
                "version_number": version.version_number,
                "media_type": version.media_type.value,
                "declared_byte_size": version.byte_size,
                "aggregate_version": asset.version,
                "duplicate_count": duplicate_count,
            },
            occurred_at=now,
            correlation_id=context.correlation_id,
        )

    @staticmethod
    def _digest(operation: SourceAssetOperationType, payload: dict[str, object]) -> str:
        encoded = json.dumps(
            {"operation": operation.value, **payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _datetime_value(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None


__all__ = [
    "SourceAssetApplicationService",
    "SourceAssetResult",
    "SourceAssetMediaType",
    "SourceAssetSourceType",
    "SourceAssetStatus",
]
