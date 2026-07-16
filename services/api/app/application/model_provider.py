from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ProviderOutcomeStatus(StrEnum):
    SUCCESS = "success"
    REFUSAL = "refusal"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ModelRequest:
    instruction_template_id: str
    instruction_template_version: str
    instructions: str
    input_text: str
    max_output_characters: int
    allow_tools: bool = False


@dataclass(frozen=True, slots=True)
class ProviderOutcome:
    status: ProviderOutcomeStatus
    output_text: str | None = None


class ModelProviderPort(Protocol):
    provider_id: str
    model_id: str

    def complete(self, request: ModelRequest) -> ProviderOutcome: ...


class DeterministicFakeProvider:
    provider_id = "fixture_fake"
    model_id = "fixture-model-v1"

    def __init__(self, outcome: ProviderOutcome) -> None:
        self.outcome = outcome
        self.last_request: ModelRequest | None = None

    def complete(self, request: ModelRequest) -> ProviderOutcome:
        self.last_request = request
        return self.outcome
