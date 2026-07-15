import json
from pathlib import Path

import pytest
from foundation_contracts import (
    STRUCTURED_BRIEF_SCHEMA_VERSION,
    validate_structured_brief,
)
from jsonschema import ValidationError

FIXTURES = Path(__file__).resolve().parents[3] / "test-fixtures" / "brief"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name", ["valid-structured-brief-v1.json", "incomplete-structured-brief-v1.json"]
)
def test_valid_structured_brief_fixtures_pass(name: str) -> None:
    validate_structured_brief(load_fixture(name))


@pytest.mark.parametrize("name", ["invalid-unknown-field.json", "invalid-schema-version.json"])
def test_invalid_structured_brief_fixtures_fail(name: str) -> None:
    with pytest.raises(ValidationError):
        validate_structured_brief(load_fixture(name))


def test_structured_brief_schema_version_is_enforced() -> None:
    assert STRUCTURED_BRIEF_SCHEMA_VERSION == "1.0.0"
