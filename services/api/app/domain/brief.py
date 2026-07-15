from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from services.api.app.domain.errors import (
    InvalidBriefMutation,
    InvalidBriefTransition,
    VersionConflict,
)


class BriefStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class BriefVersionLifecycle(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class BriefSourceType(StrEnum):
    MANUAL = "manual"
    IMPORTED_STRUCTURED = "imported_structured"


class RequirementIssueType(StrEnum):
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"
    INVALID = "invalid"
    COMPLIANCE_RISK = "compliance_risk"


class RequirementIssueSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFORMATIONAL = "informational"


class RequirementIssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class Brief:
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

    def new_version(self, *, expected_version: int, new_version_id: UUID, now: datetime) -> "Brief":
        self._require_version(expected_version)
        if self.status is BriefStatus.ARCHIVED:
            raise InvalidBriefMutation("archived briefs cannot be changed")
        return replace(
            self,
            status=BriefStatus.DRAFT,
            current_version_id=new_version_id,
            latest_version_number=self.latest_version_number + 1,
            updated_at=now,
            version=self.version + 1,
        )

    def submit(self, *, expected_version: int, now: datetime) -> "Brief":
        self._require_version(expected_version)
        if self.status is not BriefStatus.DRAFT:
            raise InvalidBriefTransition(f"cannot submit brief from {self.status}")
        return replace(self, status=BriefStatus.IN_REVIEW, updated_at=now, version=self.version + 1)

    def approve(self, *, expected_version: int, now: datetime) -> "Brief":
        self._require_version(expected_version)
        if self.status is not BriefStatus.IN_REVIEW:
            raise InvalidBriefTransition(f"cannot approve brief from {self.status}")
        return replace(self, status=BriefStatus.APPROVED, updated_at=now, version=self.version + 1)

    def archive(self, *, expected_version: int, now: datetime) -> "Brief":
        self._require_version(expected_version)
        if self.status is BriefStatus.ARCHIVED:
            raise InvalidBriefTransition("brief is already archived")
        return replace(self, status=BriefStatus.ARCHIVED, updated_at=now, version=self.version + 1)

    def touch(self, *, expected_version: int, now: datetime) -> "Brief":
        self._require_version(expected_version)
        if self.status not in {BriefStatus.DRAFT, BriefStatus.IN_REVIEW}:
            raise InvalidBriefMutation("issues on approved or archived briefs cannot be changed")
        return replace(self, updated_at=now, version=self.version + 1)

    def _require_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise VersionConflict(
                f"expected brief version {expected_version}, current version is {self.version}"
            )


@dataclass(frozen=True, slots=True)
class BriefVersion:
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
    content_schema_version: str

    def submit_for_review(self, *, now: datetime) -> "BriefVersion":
        if self.lifecycle_state is not BriefVersionLifecycle.DRAFT:
            raise InvalidBriefTransition(f"cannot submit brief version from {self.lifecycle_state}")
        return replace(
            self,
            lifecycle_state=BriefVersionLifecycle.IN_REVIEW,
            submitted_for_review_at=now,
        )

    def approve(self, *, actor_subject: str, now: datetime) -> "BriefVersion":
        if self.lifecycle_state is not BriefVersionLifecycle.IN_REVIEW:
            raise InvalidBriefTransition(
                f"cannot approve brief version from {self.lifecycle_state}"
            )
        return replace(
            self,
            lifecycle_state=BriefVersionLifecycle.APPROVED,
            approved_at=now,
            approved_by_actor_subject=actor_subject,
        )

    def supersede(self) -> "BriefVersion":
        if self.lifecycle_state not in {
            BriefVersionLifecycle.DRAFT,
            BriefVersionLifecycle.IN_REVIEW,
        }:
            raise InvalidBriefTransition(
                f"cannot supersede brief version from {self.lifecycle_state}"
            )
        return replace(self, lifecycle_state=BriefVersionLifecycle.SUPERSEDED)


@dataclass(frozen=True, slots=True)
class RequirementIssue:
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
