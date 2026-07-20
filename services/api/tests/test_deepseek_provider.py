import json

import httpx
import pytest
from pydantic import ValidationError

from services.api.app.application.model_provider import (
    DEEPSEEK_COMPLETIONS_URL,
    DeepSeekProvider,
    ModelRequest,
    ProviderOutcomeStatus,
)
from services.api.app.config import ApiSettings


def _request() -> ModelRequest:
    return ModelRequest("test", "1", "Return one JSON object only.", '{"source":true}', 100)


def _provider(handler: httpx.MockTransport) -> DeepSeekProvider:
    return DeepSeekProvider(
        api_key="test-key-not-a-secret",
        timeout_seconds=1,
        max_attempts=2,
        max_input_bytes=1024,
        max_output_bytes=1024,
        transport=handler,
    )


def test_deepseek_request_is_fixed_json_only_and_server_owned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == DEEPSEEK_COMPLETIONS_URL
        assert request.headers["authorization"] == "Bearer test-key-not-a-secret"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-flash"
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 256
        assert body["stream"] is False
        assert "tools" not in body and "tool_choice" not in body
        assert "UNTRUSTED_INPUT_BEGIN" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{}", "reasoning_content": None},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    outcome = _provider(httpx.MockTransport(handler)).complete(_request())
    assert outcome.status is ProviderOutcomeStatus.SUCCESS
    assert (outcome.input_tokens, outcome.output_tokens, outcome.total_tokens) == (1, 2, 3)


@pytest.mark.parametrize("status", [401, 403])
def test_deepseek_auth_failure_is_not_retried(status: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    assert (
        _provider(httpx.MockTransport(handler)).complete(_request()).status
        is ProviderOutcomeStatus.REFUSAL
    )
    assert calls == 1


def test_deepseek_retries_transient_failure_with_bound() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            503 if calls == 1 else 200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]},
        )

    assert (
        _provider(httpx.MockTransport(handler)).complete(_request()).status
        is ProviderOutcomeStatus.SUCCESS
    )
    assert calls == 2


def test_deepseek_malformed_or_oversized_output_fails_closed() -> None:
    malformed = _provider(httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": []})))
    assert malformed.complete(_request()).status is ProviderOutcomeStatus.ERROR
    oversized = _provider(httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 1025)))
    assert oversized.complete(_request()).status is ProviderOutcomeStatus.ERROR


@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "length", "message": {"content": "{}"}},
        {
            "finish_reason": "stop",
            "message": {"content": "{}", "reasoning_content": "not retained"},
        },
        {"finish_reason": "stop", "message": {"content": "x" * 101}},
    ],
)
def test_deepseek_completion_boundaries_fail_closed(choice: dict[str, object]) -> None:
    provider = _provider(
        httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [choice]}))
    )
    assert provider.complete(_request()).status is ProviderOutcomeStatus.ERROR


def test_deepseek_configuration_is_strict_and_default_is_offline() -> None:
    assert ApiSettings().model_provider == "deterministic_offline"
    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        ApiSettings(model_provider="deepseek")
    with pytest.raises(ValidationError, match="approved HTTPS"):
        ApiSettings(
            model_provider="deepseek",
            deepseek_api_key="x",
            deepseek_base_url="http://api.deepseek.com",
        )
    assert (
        ApiSettings(model_provider="deepseek", deepseek_api_key="x").deepseek_model
        == "deepseek-v4-flash"
    )
