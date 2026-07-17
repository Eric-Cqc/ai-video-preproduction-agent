import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from foundation_contracts import validate_structured_brief

from infra.scripts import provider_live_smoke
from services.api.app.application.brief_extraction_services import (
    PROMPT_INSTRUCTIONS,
    STRUCTURED_BRIEF_PROMPT_EXAMPLE,
    STRUCTURED_BRIEF_PROMPT_EXAMPLE_JSON,
)
from services.api.app.application.model_provider import (
    ModelRequest,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.domain.brief_issues import detect_requirement_issues

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


def _schema_invalid(field: str) -> str:
    content = json.loads(_valid())
    if field == "missing":
        del content["audience"]
    elif field == "type":
        content["deliverables"]["duration_seconds"] = ["15"]
    elif field == "enum":
        content["channels"] = ["not-a-channel"]
    elif field == "unexpected":
        content["unexpected_property"] = "generated-sensitive-value"
    elif field == "nested":
        content["brand"] = {"brand_name": "Fictional Brand"}
    return json.dumps(content)


def _failure_output(output: str, capsys: pytest.CaptureFixture[str]) -> str:
    provider = FakeProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, output))
    with pytest.raises(provider_live_smoke.SmokeFailure) as raised:
        provider_live_smoke.run_structured_brief_smoke(provider)
    error = raised.value
    assert error.category == "schema_invalid"
    provider_live_smoke._print_safe_failure(error)
    return capsys.readouterr().out


def test_prompt_example_is_production_valid_and_semantically_complete() -> None:
    assert "json" in PROMPT_INSTRUCTIONS.lower()
    assert json.loads(STRUCTURED_BRIEF_PROMPT_EXAMPLE_JSON) == STRUCTURED_BRIEF_PROMPT_EXAMPLE
    validate_structured_brief(STRUCTURED_BRIEF_PROMPT_EXAMPLE)
    assert not detect_requirement_issues(STRUCTURED_BRIEF_PROMPT_EXAMPLE)
    assert set(STRUCTURED_BRIEF_PROMPT_EXAMPLE) == {
        "schema_version",
        "objective",
        "audience",
        "offer",
        "product",
        "brand",
        "channels",
        "deliverables",
        "creative_constraints",
        "production_constraints",
        "legal_and_compliance",
        "references",
        "success_criteria",
        "open_questions",
    }
    assert STRUCTURED_BRIEF_PROMPT_EXAMPLE["channels"] == ["social"]
    assert "no Markdown fences" in PROMPT_INSTRUCTIONS
    assert "only declared properties" in PROMPT_INSTRUCTIONS


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


def test_semantic_diagnostics_expose_only_public_issue_codes() -> None:
    provider = FakeProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _semantic_invalid()))
    with pytest.raises(provider_live_smoke.SmokeFailure) as raised:
        provider_live_smoke.run_structured_brief_smoke(provider)
    assert raised.value.category == "semantic_invalid"
    assert raised.value.semantic_issue_codes == ("conflicting",)


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
    ("field", "expected_diagnostic"),
    [
        ("missing", "category=required missing=audience"),
        ("type", "category=type expected=integer"),
        ("enum", "category=enum allowed=social,digital_ad,broadcast,ecommerce,internal,other"),
        ("unexpected", "category=additionalProperties"),
        ("nested", "category=required missing=tone"),
    ],
)
def test_schema_diagnostics_are_bounded_and_do_not_expose_values(
    field: str, expected_diagnostic: str, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _failure_output(_schema_invalid(field), capsys)
    assert "Schema Validation: failed" in output
    assert expected_diagnostic in output
    assert "generated-sensitive-value" not in output
    assert _schema_invalid(field) not in output
    assert "ValidationError" not in output


def test_schema_diagnostics_cap_and_indicate_truncation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    content = json.loads(_valid())
    content["channels"] = [0] * 10
    output = _failure_output(json.dumps(content), capsys)
    assert (
        sum(
            line.startswith(f"Schema Issue {index}:")
            for line in output.splitlines()
            for index in range(1, 9)
        )
        == 8
    )
    assert "Schema Issues Truncated: true" in output


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


def test_main_suppresses_http_request_info_logs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    class LoggingProvider(FakeProvider):
        def complete(self, request: ModelRequest) -> ProviderOutcome:
            logging.getLogger("httpx").info("request body must not be emitted")
            return super().complete(request)

    provider = LoggingProvider(ProviderOutcome(ProviderOutcomeStatus.SUCCESS, _valid()))
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
    caplog.set_level(logging.INFO, logger="httpx")

    provider_live_smoke.main()

    assert "request body must not be emitted" not in caplog.text
    assert "request body must not be emitted" not in capsys.readouterr().out


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
