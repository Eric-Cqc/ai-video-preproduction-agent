from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class SourceObjectState(StrEnum):
    AVAILABLE = "available"


class SourceObjectUploadStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class SourceObject:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    source_asset_id: UUID
    source_asset_version_id: UUID
    storage_adapter: str
    storage_key: str
    state: SourceObjectState
    observed_byte_size: int
    observed_checksum_algorithm: str
    observed_checksum_value: str
    created_by_actor_subject: str
    created_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class SourceObjectUpload:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    source_asset_id: UUID
    source_asset_version_id: UUID
    source_object_id: UUID | None
    operation: str
    idempotency_key: str
    request_digest: str
    status: SourceObjectUploadStatus
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int


@dataclass(frozen=True, slots=True)
class SourceObjectCleanupRequirement:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    storage_adapter: str
    storage_key: str
    reason_code: str
    created_at: datetime
