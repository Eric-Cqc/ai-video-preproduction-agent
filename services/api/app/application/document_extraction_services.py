import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import (
    InvalidRequest,
    ResourceConflict,
    ResourceNotFound,
    StorageUnavailable,
)
from services.api.app.application.parsers import MAX_PARSER_INPUT_BYTES, parser_for_media_type
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
    EXTRACTED_DOCUMENT_SCHEMA_VERSION,
    AuditEvent,
    DocumentExtraction,
    DocumentExtractionOperation,
    DocumentExtractionOperationStatus,
    DocumentExtractionStatus,
    MembershipRole,
    OrganizationStatus,
    ProjectStatus,
    SourceAssetStatus,
    WorkspaceStatus,
)

OPTIONS_DIGEST = hashlib.sha256(b"{}").hexdigest()


@dataclass(frozen=True, slots=True)
class DocumentExtractionResult:
    extraction: DocumentExtraction
    operation: DocumentExtractionOperation
    replayed: bool


class DocumentExtractionApplicationService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        storage: StoragePort,
        *,
        clock: Clock = utc_now,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self.uow_factory = uow_factory
        self.storage = storage
        self.clock = clock
        self.id_factory = id_factory

    def create(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        *,
        idempotency_key: str,
    ) -> DocumentExtractionResult:
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
            source_object = uow.source_objects.get_for_version(
                context.organization_id,
                context.workspace_id,
                project_id,
                source_asset_id,
                source_asset_version_id,
            )
            if asset is None or version is None or source_object is None:
                raise ResourceNotFound("source object is not accessible")
            parser = parser_for_media_type(version.media_type.value)
            request_digest = self._request_digest(
                source_asset_id,
                source_asset_version_id,
                source_object.observed_checksum_value,
                parser.parser_id,
                parser.parser_version,
            )
            reservation = DocumentExtractionOperation(
                id=self.id_factory(),
                organization_id=context.organization_id,
                workspace_id=context.workspace_id,
                project_id=project_id,
                source_asset_id=source_asset_id,
                source_asset_version_id=source_asset_version_id,
                extraction_id=None,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                status=DocumentExtractionOperationStatus.RESERVED,
                submitted_by_actor_subject=context.actor_subject,
                submitted_at=self.clock(),
                completed_at=None,
                correlation_id=context.correlation_id,
                version=1,
            )
            won = uow.document_extraction_operations.reserve(reservation)
            if won is None:
                existing = uow.document_extraction_operations.get_scoped_by_key(
                    context.organization_id, context.workspace_id, project_id, idempotency_key
                )
                if existing is None:
                    raise ResourceConflict("extraction reservation could not be resolved")
                if existing.request_digest != request_digest:
                    raise ResourceConflict(
                        "idempotency key was used for a different extraction request",
                        code="idempotency_conflict",
                    )
                if (
                    existing.status is not DocumentExtractionOperationStatus.ACCEPTED
                    or existing.extraction_id is None
                ):
                    raise ResourceConflict("extraction reservation is not complete")
                extraction = uow.document_extractions.get(
                    context.organization_id,
                    context.workspace_id,
                    project_id,
                    source_asset_id,
                    source_asset_version_id,
                    existing.extraction_id,
                )
                if extraction is None:
                    raise ResourceConflict("accepted extraction outcome is unavailable")
                return DocumentExtractionResult(extraction, existing, True)

            if asset.status is not SourceAssetStatus.ACTIVE:
                raise ResourceConflict("archived source assets cannot receive new extractions")
            if source_object.storage_adapter != self.storage.adapter_name:
                raise StorageUnavailable("Object storage adapter is unavailable")
            try:
                content = self._read_bounded(self.storage.read(source_object.storage_key))
            except StorageError as error:
                raise StorageUnavailable("Object storage is unavailable") from error
            if (
                len(content) != source_object.observed_byte_size
                or hashlib.sha256(content).hexdigest() != source_object.observed_checksum_value
            ):
                raise StorageUnavailable("Stored object integrity verification failed")
            parsed = parser.parse(content, version.media_type.value)
            encoded = json.dumps(
                parsed.document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            now = self.clock()
            extraction = uow.document_extractions.add(
                DocumentExtraction(
                    id=self.id_factory(),
                    organization_id=context.organization_id,
                    workspace_id=context.workspace_id,
                    project_id=project_id,
                    source_asset_id=source_asset_id,
                    source_asset_version_id=source_asset_version_id,
                    source_object_id=source_object.id,
                    parser_id=parsed.parser_id,
                    parser_version=parsed.parser_version,
                    source_checksum_algorithm="sha256",
                    source_checksum_value=source_object.observed_checksum_value,
                    options_digest=OPTIONS_DIGEST,
                    extraction_checksum=hashlib.sha256(encoded).hexdigest(),
                    status=DocumentExtractionStatus.COMPLETED,
                    extracted_document=parsed.document,
                    character_count=parsed.character_count,
                    warning_count=parsed.warning_count,
                    truncated=parsed.truncated,
                    created_by_actor_subject=context.actor_subject,
                    created_at=now,
                    schema_version=EXTRACTED_DOCUMENT_SCHEMA_VERSION,
                )
            )
            accepted = uow.document_extraction_operations.finalize_accepted(
                won, extraction_id=extraction.id, completed_at=now, expected_version=1
            )
            uow.audit_events.append(
                AuditEvent(
                    id=self.id_factory(),
                    organization_id=context.organization_id,
                    workspace_id=context.workspace_id,
                    actor_subject=context.actor_subject,
                    aggregate_type="document_extraction",
                    aggregate_id=extraction.id,
                    action="document_extraction.completed",
                    payload={
                        "extraction_id": str(extraction.id),
                        "source_asset_id": str(source_asset_id),
                        "source_asset_version_id": str(source_asset_version_id),
                        "parser_id": parsed.parser_id,
                        "parser_version": parsed.parser_version,
                        "character_count": parsed.character_count,
                        "warning_count": parsed.warning_count,
                    },
                    occurred_at=now,
                    correlation_id=context.correlation_id,
                )
            )
            return DocumentExtractionResult(extraction, accepted, False)

    def get(
        self,
        context: TenantContext,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        extraction_id: UUID,
    ) -> DocumentExtraction:
        with self.uow_factory() as uow:
            self._require_access(uow, context, project_id, READ_ROLES)
            extraction = uow.document_extractions.get(
                context.organization_id,
                context.workspace_id,
                project_id,
                source_asset_id,
                source_asset_version_id,
                extraction_id,
            )
            if extraction is None:
                raise ResourceNotFound("document extraction is not accessible")
            return extraction

    @staticmethod
    def _read_bounded(chunks: Iterator[bytes]) -> bytes:
        content = bytearray()
        for chunk in chunks:
            content.extend(chunk)
            if len(content) > MAX_PARSER_INPUT_BYTES:
                raise InvalidRequest("source object exceeds deterministic parser input limit")
        return bytes(content)

    @staticmethod
    def _request_digest(
        asset_id: UUID, version_id: UUID, source_checksum: str, parser_id: str, parser_version: str
    ) -> str:
        encoded = json.dumps(
            {
                "source_asset_id": str(asset_id),
                "source_asset_version_id": str(version_id),
                "source_checksum": source_checksum,
                "parser_id": parser_id,
                "parser_version": parser_version,
                "options_digest": OPTIONS_DIGEST,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

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
