from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.domain import (
    BriefSourceType,
    BriefStatus,
    BriefVersionLifecycle,
    RequirementIssueSeverity,
    RequirementIssueStatus,
    RequirementIssueType,
)

SOURCE_REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"


class BriefCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    structured_content: dict[str, object]
    source_type: BriefSourceType = BriefSourceType.MANUAL
    source_reference: str | None = Field(default=None, pattern=SOURCE_REFERENCE_PATTERN)
    change_summary: str = Field(min_length=1, max_length=500)


class BriefVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_brief_version: int = Field(ge=1)
    expected_current_version_id: UUID
    source_version_id: UUID
    structured_content: dict[str, object]
    source_type: BriefSourceType = BriefSourceType.MANUAL
    source_reference: str | None = Field(default=None, pattern=SOURCE_REFERENCE_PATTERN)
    change_summary: str = Field(min_length=1, max_length=500)


class BriefTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_brief_version: int = Field(ge=1)
    expected_current_version_id: UUID


class RequirementIssueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_brief_version: int = Field(ge=1)
    expected_current_version_id: UUID
    issue_type: RequirementIssueType
    field_path: str = Field(min_length=1, max_length=300)
    severity: RequirementIssueSeverity
    message: str = Field(min_length=1, max_length=1000)


class RequirementIssueClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_brief_version: int = Field(ge=1)
    expected_current_version_id: UUID
    expected_issue_version: int = Field(ge=1)
    resolution_note: str = Field(min_length=1, max_length=1000)


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BriefResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    title: str
    status: BriefStatus
    current_version_id: UUID
    latest_version_number: int
    created_by_actor_subject: str
    created_at: datetime
    updated_at: datetime
    version: int


class BriefVersionResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    brief_id: UUID
    version_number: int
    lifecycle_state: BriefVersionLifecycle
    structured_content: dict[str, object]
    source_type: BriefSourceType
    source_reference: str | None
    change_summary: str
    created_by_actor_subject: str
    created_at: datetime
    submitted_for_review_at: datetime | None
    approved_at: datetime | None
    approved_by_actor_subject: str | None
    supersedes_version_id: UUID | None
    content_schema_version: Literal["1.0.0"]


class RequirementIssueResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    brief_id: UUID
    brief_version_id: UUID
    issue_type: RequirementIssueType
    field_path: str
    severity: RequirementIssueSeverity
    message: str
    status: RequirementIssueStatus
    resolution_note: str | None
    created_by_actor_subject: str
    resolved_by_actor_subject: str | None
    created_at: datetime
    resolved_at: datetime | None
    version: int


class BriefBundleResponse(BaseModel):
    brief: BriefResponse
    current_version: BriefVersionResponse
    issues: list[RequirementIssueResponse]


class BriefListResponse(BaseModel):
    items: list[BriefResponse]


class BriefVersionListResponse(BaseModel):
    items: list[BriefVersionResponse]


class RequirementIssueListResponse(BaseModel):
    items: list[RequirementIssueResponse]
