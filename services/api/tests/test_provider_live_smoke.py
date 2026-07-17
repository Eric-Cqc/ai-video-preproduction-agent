import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from infra.scripts import provider_live_smoke
from services.api.app.application.model_provider import (
    ModelRequest,
    ProviderOutcome,
    ProviderOutcomeStatus,
)

FIXTURE = (
    Path(__file__).parents[3]
    / "packages"
    / "test-fixtures"
    / "brief"
    / "valid-structured-brief-v1.json"
)


class FakeProvider:
    provider_id = "deepseek"
    model_id = "deepseek-v4-flash"

    def __init__(self, outcome: ProviderOutcome) -> None:
        self.outcome = outcome
        self.requests = 0

    def complete(self, request: ModelRequest) -> ProviderOutcome:
        self.requests += 1
        assert request.allow_tools is False
        return self.outcome


def _valid() -> str:
    return FIXTURE.read_text()


def _semantic_invalid() -> str:
    content = json.loads(_valid())
    content["deliverables"]["duration_seconds"] = [15, 30]
    return json.dumps(content)


def _oversized_valid() -> str:
    content = json.loads(_valid())
    content["brand"]["brand_name"] = "x" * provider_live_smoke.LIVE_SMOKE_MAX_OUTPUT_BYTES
    return json.dumps(content)


def test_live_smoke_reuses_production_structured_brief_validation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider = FakeProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _valid(), 1, 2, 3))
    summary = provider_live_smoke.run_structured_brief_smoke(provider)
    assert summary["schema_validation"] == "passed"
    assert summary["semantic_validation"] == "passed"
    assert provider.requests == 1
    assert _valid() not in capsys.readouterr().out


def test_live_smoke_rejects_semantically_invalid_structured_brief() -> None:
    provider = FakeProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _semantic_invalid()))
    with pytest.raises(provider_live_smoke.SmokeFailure, match="semantic_invalid"):
        provider_live_smoke.run_structured_brief_smoke(provider)
    assert provider.requests == 1


@pytest.mark.parametrize(
    ("output", "category"),
    [
        ("{", "malformed_output"),
        (f"```json\n{_valid()}\n```", "malformed_output"),
        (json.dumps({"schema_version": "1.0.0"}), "schema_invalid"),
        (_oversized_valid(), "output_too_large"),
    ],
)
def test_live_smoke_rejects_invalid_output_without_persistence(output: str, category: str) -> None:
    provider = FakeProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, output))
    with pytest.raises(provider_live_smoke.SmokeFailure, match=category):
        provider_live_smoke.run_structured_brief_smoke(provider)
    assert provider.requests == 1


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (ProviderOutcomeStatus.REFUSAL, "authentication_or_refusal"),
        (ProviderOutcomeStatus.TIMEOUT, "timeout"),
        (ProviderOutcomeStatus.ERROR, "provider_error"),
    ],
)
def test_live_smoke_failure_categories_are_safe(
    status: ProviderOutcomeStatus, category: str
) -> None:
    with pytest.raises(provider_live_smoke.SmokeFailure, match=category):
        provider_live_smoke.run_structured_brief_smoke(FakeProvider(ProviderOutcome(status)))


def test_live_smoke_rejects_malformed_usage_metadata() -> None:
    provider = FakeProvider(
        ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _valid(), input_tokens=True)
    )
    with pytest.raises(provider_live_smoke.SmokeFailure, match="malformed_usage_metadata"):
        provider_live_smoke.run_structured_brief_smoke(provider)


def test_missing_opt_in_blocks_before_settings_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_PROVIDER_LIVE_SMOKE", raising=False)
    with pytest.raises(SystemExit, match="ALLOW_PROVIDER_LIVE_SMOKE"):
        provider_live_smoke.main()


def test_main_prints_only_the_safe_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    provider = FakeProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _valid(), 1, 2, 3))
    monkeypatch.setenv("ALLOW_PROVIDER_LIVE_SMOKE", "1")
    monkeypatch.setattr(
        provider_live_smoke,
        "ApiSettings",
        lambda: SimpleNamespace(
            model_provider="deepseek",
            deepseek_api_key="fixture-only-value",
            deepseek_timeout_seconds=1,
        ),
    )
    monkeypatch.setattr(provider_live_smoke, "DeepSeekProvider", lambda **_kwargs: provider)

    provider_live_smoke.main()

    output = capsys.readouterr().out
    assert set(line.partition(":")[0] for line in output.splitlines()) == {
        "Provider",
        "Model",
        "Capability",
        "Authentication",
        "Json Parse",
        "Schema Validation",
        "Semantic Validation",
        "Input Tokens",
        "Output Tokens",
        "Total Tokens",
    }
    assert "fixture-only-value" not in output
    assert provider_live_smoke.SYNTHETIC_BRIEF_SOURCE not in output
    assert _valid() not in output


@pytest.mark.parametrize(
    ("model_provider", "api_key"),
    [("deterministic_offline", None), ("deepseek", None)],
)
def test_invalid_provider_configuration_blocks_before_network(
    monkeypatch: pytest.MonkeyPatch, model_provider: str, api_key: str | None
) -> None:
    monkeypatch.setenv("ALLOW_PROVIDER_LIVE_SMOKE", "1")
    monkeypatch.setattr(
        provider_live_smoke,
        "ApiSettings",
        lambda: SimpleNamespace(model_provider=model_provider, deepseek_api_key=api_key),
    )
    monkeypatch.setattr(
        provider_live_smoke,
        "DeepSeekProvider",
        lambda **_kwargs: pytest.fail("Provider construction must not occur"),
    )
    with pytest.raises(SystemExit, match="MODEL_PROVIDER=deepseek"):
        provider_live_smoke.main()
