from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class BriefExtractionRunStatus(StrEnum):
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    FAILED = "failed"


class BriefExtractionAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    MALFORMED_OUTPUT = "malformed_output"
    SCHEMA_INVALID = "schema_invalid"
    REFUSED = "refused"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"


class BriefCandidateReviewAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class BriefCandidateReviewStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class BriefCandidateRejectReason(StrEnum):
    INACCURATE = "inaccurate"
    INCOMPLETE = "incomplete"
    UNSAFE = "unsafe"
    IRRELEVANT = "irrelevant"
    DUPLICATE = "duplicate"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class BriefExtractionRun:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    document_extraction_id: UUID
    provider_id: str
    model_id: str
    prompt_template_id: str
    prompt_template_version: str
    input_extraction_checksum: str
    status: BriefExtractionRunStatus
    candidate_structured_brief: dict[str, object] | None
    candidate_digest: str | None
    candidate_issues: list[dict[str, object]]
    created_by_actor_subject: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BriefExtractionAttempt:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    run_id: UUID
    attempt_number: int
    status: BriefExtractionAttemptStatus
    output_digest: str | None
    error_code: str | None
    input_character_count: int
    output_character_count: int
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class BriefCandidateReview:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    brief_extraction_run_id: UUID
    action: BriefCandidateReviewAction
    status: BriefCandidateReviewStatus
    idempotency_key: str
    request_digest: str
    candidate_digest: str
    accepted_content_digest: str | None
    accepted_content_modified: bool | None
    brief_id: UUID | None
    brief_version_id: UUID | None
    rejection_reason: BriefCandidateRejectReason | None
    rejection_note: str | None
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int
