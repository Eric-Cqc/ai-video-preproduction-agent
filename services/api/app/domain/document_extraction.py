from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

EXTRACTED_DOCUMENT_SCHEMA_VERSION = "1.0.0"


class DocumentExtractionStatus(StrEnum):
    COMPLETED = "completed"


class DocumentExtractionOperationStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class DocumentExtraction:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    source_asset_id: UUID
    source_asset_version_id: UUID
    source_object_id: UUID
    parser_id: str
    parser_version: str
    source_checksum_algorithm: str
    source_checksum_value: str
    options_digest: str
    extraction_checksum: str
    status: DocumentExtractionStatus
    extracted_document: dict[str, object]
    character_count: int
    warning_count: int
    truncated: bool
    created_by_actor_subject: str
    created_at: datetime
    schema_version: str


@dataclass(frozen=True, slots=True)
class DocumentExtractionOperation:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    source_asset_id: UUID
    source_asset_version_id: UUID
    extraction_id: UUID | None
    idempotency_key: str
    request_digest: str
    status: DocumentExtractionOperationStatus
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int
