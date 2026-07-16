from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.domain import (
    BriefCandidateRejectReason,
    BriefCandidateReviewAction,
    BriefCandidateReviewStatus,
)


class CandidateAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief_id: UUID | None = None
    expected_brief_version: int | None = Field(default=None, ge=1)
    expected_current_version_id: UUID | None = None
    accepted_content: dict[str, object] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)


class CandidateRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: BriefCandidateRejectReason
    note: str | None = Field(default=None, max_length=500)


class CandidateRunResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime


class CandidateContentResponse(BaseModel):
    run_id: UUID
    candidate: dict[str, object]
    candidate_issues: list[dict[str, object]]


class CandidateReviewResponse(BaseModel):
    review_id: UUID
    action: BriefCandidateReviewAction
    status: BriefCandidateReviewStatus
    brief_id: UUID | None
    brief_version_id: UUID | None
    replayed: bool
    completed_at: datetime | None
