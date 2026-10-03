from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from services.api.app.domain.errors import InvalidBriefMutation, VersionConflict


class IdeaIntakeStatus(StrEnum):
    STRUCTURED = "structured"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class IdeaIntake:
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

    def patch(
        self,
        *,
        expected_version: int,
        objective: str | None,
        platform: str | None,
        audience: str | None,
        duration_seconds: int | None,
        content_type: str | None,
        tone: list[str],
        key_messages: list[str],
        call_to_action: str | None,
        constraints: list[str],
        must_include: list[str],
        must_avoid: list[str],
        assumptions: list[str],
        missing_fields: list[str],
        now: datetime,
    ) -> "IdeaIntake":
        self._require_version(expected_version)
        if self.status is IdeaIntakeStatus.CONFIRMED:
            raise InvalidBriefMutation("confirmed idea intakes cannot be edited")
        return replace(
            self,
            objective=objective,
            platform=platform,
            audience=audience,
            duration_seconds=duration_seconds,
            content_type=content_type,
            tone=tone,
            key_messages=key_messages,
            call_to_action=call_to_action,
            constraints=constraints,
            must_include=must_include,
            must_avoid=must_avoid,
            assumptions=assumptions,
            missing_fields=missing_fields,
            updated_at=now,
            version=self.version + 1,
        )

    def confirm(
        self,
        *,
        expected_version: int,
        brief_id: UUID,
        brief_version_id: UUID,
        now: datetime,
    ) -> "IdeaIntake":
        self._require_version(expected_version)
        if self.status is IdeaIntakeStatus.CONFIRMED:
            raise InvalidBriefMutation("idea intake is already confirmed")
        return replace(
            self,
            status=IdeaIntakeStatus.CONFIRMED,
            brief_id=brief_id,
            brief_version_id=brief_version_id,
            updated_at=now,
            version=self.version + 1,
        )

    def _require_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise VersionConflict(
                "expected idea intake version "
                f"{expected_version}, current version is {self.version}"
            )
