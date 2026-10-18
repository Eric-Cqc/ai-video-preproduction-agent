from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.domain import IdeaIntakeStatus
from services.api.app.presentation.brief_schemas import BriefBundleResponse


class IdeaIntakeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea: str = Field(min_length=1, max_length=8000)


class IdeaIntakePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    objective: str | None = Field(default=None, max_length=500)
    platform: str | None = Field(default=None, max_length=120)
    audience: str | None = Field(default=None, max_length=500)
    duration_seconds: int | None = Field(default=None, ge=15, le=60)
    content_type: str | None = Field(default=None, max_length=120)
    tone: list[str] = Field(default_factory=list, max_length=10)
    key_messages: list[str] = Field(default_factory=list, max_length=20)
    call_to_action: str | None = Field(default=None, max_length=500)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    must_include: list[str] = Field(default_factory=list, max_length=20)
    must_avoid: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    missing_fields: list[str] = Field(default_factory=list, max_length=3)


class IdeaIntakeConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IdeaIntakeResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    raw_idea: str
    objective: str | None
    platform: str | None
    audience: str | None
    duration_seconds: int | None
    content_type: str | None
    tone: list[str]
    key_messages: list[str]
    call_to_action: str | None
    constraints: list[str]
    must_include: list[str]
    must_avoid: list[str]
    assumptions: list[str]
    missing_fields: list[str]
    status: IdeaIntakeStatus
    brief_id: UUID | None
    brief_version_id: UUID | None
    created_by_actor_subject: str
    created_at: datetime
    updated_at: datetime
    version: int


class IdeaIntakeListResponse(BaseModel):
    items: list[IdeaIntakeResponse]


class IdeaIntakeConfirmationResponse(BaseModel):
    idea_intake: IdeaIntakeResponse
    result: BriefBundleResponse
