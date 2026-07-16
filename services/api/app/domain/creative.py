from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CreativeGenerationOperationType(StrEnum):
    GENERATE_CONCEPTS = "generate_creative_concepts"
    SELECT_CONCEPT = "select_creative_concept"
    GENERATE_SCRIPT = "generate_script"
    GENERATE_STORYBOARD = "generate_storyboard"
    GENERATE_SHOT_PLAN = "generate_shot_plan"


class CreativeGenerationOperationStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class CreativeGenerationOperation:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    operation: CreativeGenerationOperationType
    idempotency_key: str
    request_digest: str
    status: CreativeGenerationOperationStatus
    outcome_concept_run_id: UUID | None
    outcome_candidate_id: UUID | None
    outcome_selection_id: UUID | None
    outcome_script_run_id: UUID | None
    outcome_script_version_id: UUID | None
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int


class CreativeRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CreativeConceptRun:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    brief_id: UUID
    brief_version_id: UUID
    brief_content_digest: str
    instruction_template_id: str
    instruction_template_version: str
    provider_id: str
    model_id: str
    request_digest: str
    status: CreativeRunStatus
    failure_category: str | None
    candidate_count: int
    created_by_actor_subject: str
    created_at: datetime
    completed_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class CreativeConceptCandidate:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    concept_run_id: UUID
    candidate_index: int
    schema_version: str
    content: dict[str, object]
    content_digest: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CreativeConceptSelection:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    concept_run_id: UUID
    concept_candidate_id: UUID
    selected_by_actor_subject: str
    selected_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class ScriptRun:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    brief_id: UUID
    brief_version_id: UUID
    concept_run_id: UUID
    concept_candidate_id: UUID
    concept_selection_id: UUID
    brief_content_digest: str
    concept_content_digest: str
    instruction_template_id: str
    instruction_template_version: str
    provider_id: str
    model_id: str
    request_digest: str
    status: CreativeRunStatus
    failure_category: str | None
    created_by_actor_subject: str
    created_at: datetime
    completed_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class ScriptVersion:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    script_run_id: UUID
    brief_id: UUID
    brief_version_id: UUID
    concept_run_id: UUID
    concept_candidate_id: UUID
    concept_selection_id: UUID
    version_number: int
    schema_version: str
    content: dict[str, object]
    content_digest: str
    created_at: datetime
