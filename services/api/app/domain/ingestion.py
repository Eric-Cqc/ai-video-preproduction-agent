from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class BriefIngestionOperation(StrEnum):
    CREATE_BRIEF = "create_brief"
    CREATE_VERSION = "create_version"


class BriefIngestionSourceType(StrEnum):
    IMPORTED_STRUCTURED = "imported_structured"
    API_STRUCTURED = "api_structured"


class BriefIngestionStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class BriefIngestion:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    brief_id: UUID | None
    brief_version_id: UUID | None
    operation: BriefIngestionOperation
    idempotency_key: str
    source_type: BriefIngestionSourceType
    source_reference: str | None
    payload_digest: str
    schema_version: str
    status: BriefIngestionStatus
    rejection_code: str | None
    rejection_details: str | None
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int
