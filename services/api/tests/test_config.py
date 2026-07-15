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


def test_database_configuration_requires_postgresql_and_production_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        ApiSettings(app_environment="production")
    with pytest.raises(ValidationError):
        ApiSettings(database_url="sqlite:///foundation.db")


def test_database_credentials_are_redacted() -> None:
    settings = ApiSettings(
        app_environment="test",
        database_url="postgresql+psycopg://user:secret@localhost/foundation_test",
    )
    assert "secret" not in settings.redacted_database_url
    assert "***" in settings.redacted_database_url
