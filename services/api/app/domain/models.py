from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from services.api.app.domain.errors import (
    InvalidProjectMutation,
    InvalidProjectTransition,
    VersionConflict,
)


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Organization:
    id: UUID
    slug: str
    name: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    organization_id: UUID
    slug: str
    name: str
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class Membership:
    id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    actor_subject: str
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class Project:
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

    def update_details(
        self,
        *,
        expected_version: int,
        changed_fields: frozenset[str],
        name: str | None,
        description: str | None,
        now: datetime,
    ) -> "Project":
        self._require_version(expected_version)
        if self.status is ProjectStatus.ARCHIVED:
            raise InvalidProjectMutation("archived projects cannot be changed")
        if not changed_fields or not changed_fields <= {"name", "description"}:
            raise InvalidProjectMutation("at least one supported field must change")

        next_name = name if "name" in changed_fields else self.name
        next_description = description if "description" in changed_fields else self.description
        if next_name is None or not next_name.strip():
            raise InvalidProjectMutation("project name must not be empty")
        if next_name == self.name and next_description == self.description:
            raise InvalidProjectMutation("project mutation contains no changes")
        return replace(
            self,
            name=next_name,
            description=next_description,
            updated_at=now,
            version=self.version + 1,
        )

    def activate(self, *, expected_version: int, now: datetime) -> "Project":
        self._require_version(expected_version)
        if self.status is not ProjectStatus.DRAFT:
            raise InvalidProjectTransition(f"cannot activate project from {self.status}")
        return replace(
            self,
            status=ProjectStatus.ACTIVE,
            updated_at=now,
            version=self.version + 1,
        )

    def archive(self, *, expected_version: int, now: datetime) -> "Project":
        self._require_version(expected_version)
        if self.status not in {ProjectStatus.DRAFT, ProjectStatus.ACTIVE}:
            raise InvalidProjectTransition(f"cannot archive project from {self.status}")
        return replace(
            self,
            status=ProjectStatus.ARCHIVED,
            updated_at=now,
            version=self.version + 1,
        )

    def _require_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise VersionConflict(
                f"expected project version {expected_version}, current version is {self.version}"
            )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    actor_subject: str
    aggregate_type: str
    aggregate_id: UUID
    action: str
    payload: dict[str, object]
    occurred_at: datetime
    correlation_id: str
    causation_id: str | None = None
