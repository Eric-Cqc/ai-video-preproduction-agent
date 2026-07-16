from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReviewArtifactTypeLiteral = Literal["script", "storyboard", "shot_plan", "planning_bundle"]
ReviewOutcomeLiteral = Literal["approved", "revision_requested", "rejected"]
RevisionModeLiteral = Literal[
    "valid",
    "malformed",
    "schema_invalid",
    "duration_invalid",
    "refusal",
    "timeout",
    "provider_error",
    "scene_mismatch",
    "shot_order_invalid",
    "scene_coverage_invalid",
    "continuity_invalid",
]
ExportFormatLiteral = Literal[
    "manifest.json",
    "script.json",
    "storyboard.json",
    "shot-plan.json",
    "shot-plan.csv",
    "README.txt",
    "delivery-package.zip",
]


class PlanningReviewSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: ReviewArtifactTypeLiteral
    script_version_id: UUID | None = None
    storyboard_version_id: UUID | None = None
    shot_plan_version_id: UUID | None = None
    outcome: ReviewOutcomeLiteral
    summary: str = Field(min_length=1, max_length=1000)
    requested_changes: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_artifact_pair(self) -> "PlanningReviewSubmitRequest":
        values = [self.script_version_id, self.storyboard_version_id, self.shot_plan_version_id]
        expected = {"script": 0, "storyboard": 1, "shot_plan": 2, "planning_bundle": 3}[
            self.artifact_type
        ]
        if sum(value is not None for value in values) != (3 if expected == 3 else 1):
            raise ValueError("artifact version IDs do not match artifact_type")
        if expected < 3 and values[expected] is None:
            raise ValueError("artifact version ID is required")
        if self.outcome != "revision_requested" and self.requested_changes:
            raise ValueError("requested_changes requires revision_requested")
        return self


class RevisionCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_mode: RevisionModeLiteral = "valid"


class DeliveryPackageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    script_version_id: UUID
    storyboard_version_id: UUID
    shot_plan_version_id: UUID
    approval_review_id: UUID


class DeliveryExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: ExportFormatLiteral
