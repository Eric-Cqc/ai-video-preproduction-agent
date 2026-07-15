import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from model_registry import DuplicateProviderError, ProviderCapability, ProviderRegistry
from pydantic import ValidationError

CAPABILITY_FIXTURE = Path(__file__).resolve().parents[2] / "test-fixtures" / "model-capability.json"


@dataclass(frozen=True)
class FakeAdapter:
    capability: ProviderCapability


def load_capability() -> ProviderCapability:
    payload = json.loads(CAPABILITY_FIXTURE.read_text(encoding="utf-8"))
    return ProviderCapability.model_validate(payload)


def test_adapter_registration() -> None:
    registry = ProviderRegistry()
    adapter = FakeAdapter(load_capability())
    registry.register(adapter)
    assert len(registry) == 1
    assert registry.get("example-provider") is adapter


def test_duplicate_identifier_is_rejected() -> None:
    registry = ProviderRegistry()
    registry.register(FakeAdapter(load_capability()))
    with pytest.raises(DuplicateProviderError):
        registry.register(FakeAdapter(load_capability()))


def test_capability_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderCapability.model_validate(
            {
                "identifier": "example-provider",
                "modalities": ["video"],
                "asynchronous": True,
                "api_key": "must-not-be-accepted",
            }
        )
