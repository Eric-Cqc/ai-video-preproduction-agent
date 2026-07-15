from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.api.app.domain import (
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    ProjectStatus,
    WorkspaceStatus,
)

SLUG_PATTERN = r"^[a-z][a-z0-9-]{1,62}$"
ACTOR_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,199}$"


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=200)


class OrganizationResponse(DomainResponse):
    id: UUID
    slug: str
    name: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime
    version: int


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=200)


class WorkspaceResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    slug: str
    name: str
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime
    version: int


class MembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_subject: str = Field(pattern=ACTOR_PATTERN)
    role: Literal[MembershipRole.ADMIN, MembershipRole.MEMBER, MembershipRole.VIEWER]


class MembershipResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    actor_subject: str
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime
    version: int


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def require_mutation(self) -> "ProjectPatch":
        changed_fields = self.model_fields_set - {"expected_version"}
        if not changed_fields:
            raise ValueError("PATCH requires name or description")
        if "name" in changed_fields and self.name is None:
            raise ValueError("name cannot be null")
        return self


class ProjectTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class ProjectResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_by_actor_subject: str
    created_at: datetime
    updated_at: datetime
    version: int


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


class AuditEventResponse(DomainResponse):
    id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    actor_subject: str
    aggregate_type: str
    aggregate_id: UUID
    action: str
    payload: dict[str, Any]
    occurred_at: datetime
    correlation_id: str
    causation_id: str | None


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
