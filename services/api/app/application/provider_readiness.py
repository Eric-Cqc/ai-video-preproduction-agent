"""Static, offline-only boundary for any future provider integration."""

from dataclasses import dataclass
from enum import StrEnum


class ProviderExecutionMode(StrEnum):
    DETERMINISTIC_OFFLINE = "deterministic_offline"
    REMOTE = "remote"


class ProviderFailureClass(StrEnum):
    TIMEOUT = "timeout"
    TRANSIENT_ERROR = "transient_error"
    REFUSAL = "refusal"
    MALFORMED_OUTPUT = "malformed_output"
    SCHEMA_INVALID = "schema_invalid"
    SEMANTIC_INVALID = "semantic_invalid"
    SECURITY_REJECTION = "security_rejection"


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider_id: str
    model_id: str
    capability: str
    execution_mode: ProviderExecutionMode
    supported_schema_versions: frozenset[str]
    max_input_bytes: int
    max_output_bytes: int
    timeout_class: ProviderFailureClass = ProviderFailureClass.TIMEOUT
    supports_tools: bool = False
    supports_external_fetch: bool = False


OFFLINE_CAPABILITIES = (
    ProviderCapability(
        "fixture_fake",
        "fixture-model-v1",
        "brief_extraction",
        ProviderExecutionMode.DETERMINISTIC_OFFLINE,
        frozenset({"structured-brief-v1", "creative-concept-v1", "script-v1"}),
        131_072,
        131_072,
    ),
    ProviderCapability(
        "fixture_visual_planning",
        "fixture-visual-v1",
        "storyboard",
        ProviderExecutionMode.DETERMINISTIC_OFFLINE,
        frozenset({"storyboard-v1"}),
        131_072,
        131_072,
    ),
    ProviderCapability(
        "fixture_visual_planning",
        "fixture-visual-v1",
        "shot_plan",
        ProviderExecutionMode.DETERMINISTIC_OFFLINE,
        frozenset({"shot-plan-v1"}),
        131_072,
        131_072,
    ),
    ProviderCapability(
        "fixture_revision",
        "fixture-revision-v1",
        "revision",
        ProviderExecutionMode.DETERMINISTIC_OFFLINE,
        frozenset({"script-v1", "storyboard-v1", "shot-plan-v1"}),
        131_072,
        131_072,
    ),
)


def require_offline_capability(provider_id: str, capability: str) -> ProviderCapability:
    for candidate in OFFLINE_CAPABILITIES:
        if candidate.provider_id == provider_id and candidate.capability == capability:
            if candidate.supports_tools or candidate.supports_external_fetch:
                raise ValueError("offline providers may not use tools or external fetch")
            return candidate
    raise ValueError("unknown or remote provider is not enabled")


def is_retryable(failure: ProviderFailureClass) -> bool:
    return failure in {ProviderFailureClass.TIMEOUT, ProviderFailureClass.TRANSIENT_ERROR}


def validate_secret_reference(reference: str) -> str:
    if not reference or not reference.replace("_", "").isalnum() or not reference.isupper():
        raise ValueError("secret references must be uppercase environment variable names")
    return reference
