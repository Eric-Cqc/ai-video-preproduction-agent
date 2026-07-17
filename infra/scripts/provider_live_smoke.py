"""Explicit in-memory Structured Brief smoke; never prints sensitive content."""

import logging
import os

from services.api.app.application.brief_extraction_services import (
    PROMPT_INSTRUCTIONS,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_VERSION,
    SchemaDiagnostic,
    StructuredBriefSchemaInvalid,
    StructuredBriefSemanticInvalid,
    validate_structured_brief_provider_output,
)
from services.api.app.application.errors import InvalidRequest
from services.api.app.application.model_provider import (
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_PROVIDER_ID,
    DeepSeekProvider,
    ModelProviderPort,
    ModelRequest,
    ProviderOutcome,
    ProviderOutcomeStatus,
)
from services.api.app.config import ApiSettings

SYNTHETIC_BRIEF_SOURCE = (
    "Create a 15-second product explainer structured brief for a fictional reusable notebook. "
    "Use only generic, fictional information."
)
LIVE_SMOKE_MAX_INPUT_BYTES = 1024
LIVE_SMOKE_MAX_OUTPUT_BYTES = 4096


class SmokeFailure(RuntimeError):
    """A bounded category suitable for terminal output."""

    def __init__(
        self,
        category: str,
        *,
        schema_diagnostics: tuple[SchemaDiagnostic, ...] = (),
        schema_issue_count: int = 0,
        schema_truncated: bool = False,
        semantic_issue_codes: tuple[str, ...] = (),
    ) -> None:
        super().__init__(category)
        self.category = category
        self.schema_diagnostics = schema_diagnostics
        self.schema_issue_count = schema_issue_count
        self.schema_truncated = schema_truncated
        self.semantic_issue_codes = semantic_issue_codes


def run_structured_brief_smoke(provider: ModelProviderPort) -> dict[str, int | str]:
    if provider.provider_id != DEEPSEEK_PROVIDER_ID or provider.model_id != DEEPSEEK_MODEL_ID:
        raise SmokeFailure("unexpected_provider_identity")
    request = ModelRequest(
        PROMPT_TEMPLATE_ID,
        PROMPT_TEMPLATE_VERSION,
        PROMPT_INSTRUCTIONS,
        SYNTHETIC_BRIEF_SOURCE,
        LIVE_SMOKE_MAX_OUTPUT_BYTES,
        False,
    )
    if len(request.input_text.encode()) > LIVE_SMOKE_MAX_INPUT_BYTES:
        raise SmokeFailure("input_too_large")
    outcome = provider.complete(request)
    _require_success(outcome)
    if (
        outcome.output_text is not None
        and len(outcome.output_text.encode()) > LIVE_SMOKE_MAX_OUTPUT_BYTES
    ):
        raise SmokeFailure("output_too_large")
    try:
        validate_structured_brief_provider_output(
            outcome.output_text, require_no_blocking_issues=True
        )
    except StructuredBriefSchemaInvalid as error:
        raise SmokeFailure(
            "schema_invalid",
            schema_diagnostics=error.diagnostics.issues,
            schema_issue_count=error.diagnostics.total_count,
            schema_truncated=error.diagnostics.truncated,
        ) from None
    except StructuredBriefSemanticInvalid as error:
        raise SmokeFailure("semantic_invalid", semantic_issue_codes=error.issue_codes) from None
    except InvalidRequest as error:
        raise SmokeFailure(error.code) from None
    return {
        "provider": provider.provider_id,
        "model": provider.model_id,
        "capability": "structured-brief",
        "authentication": "accepted",
        "json_parse": "passed",
        "schema_validation": "passed",
        "semantic_validation": "passed",
        "input_tokens": _usage(outcome.input_tokens),
        "output_tokens": _usage(outcome.output_tokens),
        "total_tokens": _usage(outcome.total_tokens),
    }


def _require_success(outcome: ProviderOutcome) -> None:
    if outcome.status is ProviderOutcomeStatus.REFUSAL:
        raise SmokeFailure("authentication_or_refusal")
    if outcome.status is ProviderOutcomeStatus.TIMEOUT:
        raise SmokeFailure("timeout")
    if outcome.status is not ProviderOutcomeStatus.SUCCESS:
        raise SmokeFailure("provider_error")


def _usage(value: object) -> int | str:
    if value is None:
        return "unavailable"
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10_000_000:
        return value
    raise SmokeFailure("malformed_usage_metadata")


def main() -> None:
    if os.environ.get("ALLOW_PROVIDER_LIVE_SMOKE") != "1":
        raise SystemExit("set ALLOW_PROVIDER_LIVE_SMOKE=1; this command may incur API cost")
    settings = ApiSettings()
    if settings.model_provider != "deepseek" or not settings.deepseek_api_key:
        raise SystemExit("set MODEL_PROVIDER=deepseek and DEEPSEEK_API_KEY before live smoke")
    _suppress_transport_info_logs()
    provider = DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        timeout_seconds=settings.deepseek_timeout_seconds,
        max_attempts=1,
        max_input_bytes=LIVE_SMOKE_MAX_INPUT_BYTES,
        max_output_bytes=LIVE_SMOKE_MAX_OUTPUT_BYTES,
    )
    try:
        summary = run_structured_brief_smoke(provider)
    except SmokeFailure as error:
        _print_safe_failure(error)
        raise SystemExit(1) from None
    for label, value in summary.items():
        print(f"{label.replace('_', ' ').title()}: {value}")


def _suppress_transport_info_logs() -> None:
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _print_safe_failure(error: SmokeFailure) -> None:
    print(f"Provider live smoke failed safely: {error.category}")
    if error.category == "schema_invalid":
        print("Schema Validation: failed")
        print(f"Schema Issue Count: {error.schema_issue_count}")
        for index, issue in enumerate(error.schema_diagnostics, start=1):
            _print_schema_diagnostic(index, issue)
        if error.schema_truncated:
            print("Schema Issues Truncated: true")
    if error.category == "semantic_invalid":
        print("Semantic Validation: failed")
        print(f"Semantic Issue Count: {len(error.semantic_issue_codes)}")
        for index, issue_code in enumerate(error.semantic_issue_codes[:8], start=1):
            print(f"Semantic Issue {index}: code={issue_code}")


def _print_schema_diagnostic(index: int, issue: SchemaDiagnostic) -> None:
    parts = [f"Schema Issue {index}: path={issue.path}", f"category={issue.category}"]
    if issue.missing_property is not None:
        parts.append(f"missing={issue.missing_property}")
    if issue.expected_type is not None:
        parts.append(f"expected={issue.expected_type}")
    if issue.allowed_values:
        parts.append(f"allowed={','.join(issue.allowed_values)}")
    print(" ".join(parts))


if __name__ == "__main__":
    main()
