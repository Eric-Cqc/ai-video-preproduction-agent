import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

MAX_REQUESTED_CHANGES_BYTES = 16 * 1024
MAX_REQUESTED_CHANGES_DEPTH = 8


class PlanningReviewSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: ReviewArtifactTypeLiteral
    script_version_id: UUID | None = None
    storyboard_version_id: UUID | None = None
    shot_plan_version_id: UUID | None = None
    outcome: ReviewOutcomeLiteral
    summary: str = Field(min_length=1, max_length=1000)
    requested_changes: dict[str, object] = Field(default_factory=dict)

    @field_validator("requested_changes")
    @classmethod
    def validate_requested_changes_bounds(cls, value: dict[str, object]) -> dict[str, object]:
        try:
            serialized = json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        except (TypeError, ValueError) as error:
            raise ValueError("requested_changes must contain JSON values") from error
        if len(serialized) > MAX_REQUESTED_CHANGES_BYTES:
            raise ValueError("requested_changes exceeds the maximum serialized size")
        if _max_container_depth(value) > MAX_REQUESTED_CHANGES_DEPTH:
            raise ValueError("requested_changes exceeds the maximum nesting depth")
        return value

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


def _max_container_depth(value: object) -> int:
    maximum = 0
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if not isinstance(current, (dict, list, tuple)):
            continue
        current_depth = depth + 1
        maximum = max(maximum, current_depth)
        children = current.values() if isinstance(current, dict) else current
        pending.extend((child, current_depth) for child in children)
    return maximum


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
