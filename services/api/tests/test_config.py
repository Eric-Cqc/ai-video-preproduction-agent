import pytest
from pydantic import ValidationError

from services.api.app.config import ApiSettings


def test_explicit_cors_origins_are_normalized() -> None:
    settings = ApiSettings(api_allowed_cors_origins="http://localhost:3000, https://example.test")
    assert settings.allowed_cors_origins == ["http://localhost:3000", "https://example.test"]


@pytest.mark.parametrize("value", ["*", "", "javascript:alert(1)", "https://user:pass@test"])
def test_unsafe_cors_configuration_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        ApiSettings(api_allowed_cors_origins=value)
