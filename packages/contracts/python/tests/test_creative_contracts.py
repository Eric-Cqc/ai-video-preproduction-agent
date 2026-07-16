import json
from pathlib import Path

import pytest
from foundation_contracts.creative import (
    validate_creative_concept,
    validate_script,
)
from jsonschema import ValidationError

FIXTURES = Path(__file__).parents[3] / "test-fixtures" / "creative"


def test_concept_contract_accepts_canonical_fixture() -> None:
    validate_creative_concept(json.loads((FIXTURES / "valid-concept-v1.json").read_text()))


def test_concept_contract_rejects_invalid_fixture() -> None:
    with pytest.raises(ValidationError):
        validate_creative_concept(json.loads((FIXTURES / "invalid-concept-v1.json").read_text()))


def test_script_contract_accepts_canonical_fixture() -> None:
    validate_script(json.loads((FIXTURES / "valid-script-v1.json").read_text()))
