import json
from pathlib import Path

import pytest
from foundation_contracts import HEALTH_CONTRACT_VERSION, validate_health_response
from jsonschema import ValidationError

FIXTURES = Path(__file__).resolve().parents[3] / "test-fixtures" / "health"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_valid_health_fixture_passes() -> None:
    validate_health_response(load_fixture("valid-health.json"))


def test_invalid_health_fixture_fails() -> None:
    with pytest.raises(ValidationError):
        validate_health_response(load_fixture("invalid-health.json"))


def test_contract_version_is_enforced() -> None:
    payload = load_fixture("valid-health.json")
    assert isinstance(payload, dict)
    payload["contract_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        validate_health_response(payload)
    assert HEALTH_CONTRACT_VERSION == "1.0.0"
