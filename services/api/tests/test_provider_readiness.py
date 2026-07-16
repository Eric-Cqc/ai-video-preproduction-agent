import pytest

from services.api.app.application.provider_readiness import (
    ProviderFailureClass,
    is_retryable,
    require_offline_capability,
    validate_secret_reference,
)


def test_offline_capability_rejects_remote_and_tool_like_requests() -> None:
    capability = require_offline_capability("fixture_visual_planning", "storyboard")
    assert not capability.supports_tools
    assert not capability.supports_external_fetch
    with pytest.raises(ValueError, match="unknown or remote"):
        require_offline_capability("remote-provider", "storyboard")


def test_retry_and_secret_boundaries_are_bounded() -> None:
    assert is_retryable(ProviderFailureClass.TIMEOUT)
    assert is_retryable(ProviderFailureClass.TRANSIENT_ERROR)
    assert not is_retryable(ProviderFailureClass.REFUSAL)
    assert validate_secret_reference("FUTURE_PROVIDER_TOKEN") == "FUTURE_PROVIDER_TOKEN"
    with pytest.raises(ValueError):
        validate_secret_reference("token-value")
