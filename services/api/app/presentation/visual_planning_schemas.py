from typing import Literal

from pydantic import BaseModel, ConfigDict

StoryboardProviderMode = Literal[
    "valid",
    "malformed_json",
    "markdown_wrapped",
    "schema_invalid",
    "missing_scene",
    "extra_scene",
    "duplicate_scene_number",
    "non_consecutive_scene_number",
    "script_scene_mismatch",
    "duration_mismatch",
    "excessive_duration",
    "unsafe_visual_prompt_content",
    "refusal",
    "timeout",
    "provider_error",
    "prompt_injection",
]
ShotPlanProviderMode = Literal[
    "valid",
    "malformed_json",
    "markdown_wrapped",
    "schema_invalid",
    "duplicate_shot_id",
    "duplicate_shot_order",
    "non_consecutive_shot_order",
    "invalid_scene_reference",
    "missing_scene_coverage",
    "storyboard_scene_mismatch",
    "duration_mismatch",
    "continuity_break",
    "excessive_shot_count",
    "unsafe_visual_prompt_content",
    "refusal",
    "timeout",
    "provider_error",
    "prompt_injection",
]


class StoryboardGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_mode: StoryboardProviderMode = "valid"


class ShotPlanGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_mode: ShotPlanProviderMode = "valid"


StoryboardGenerateRequest = StoryboardGenerationRequest
ShotPlanGenerateRequest = ShotPlanGenerationRequest
