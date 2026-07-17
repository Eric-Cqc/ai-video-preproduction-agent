"""Explicit in-memory Structured Brief smoke; never prints sensitive content."""

import os

from services.api.app.application.brief_extraction_services import (
    PROMPT_INSTRUCTIONS,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_VERSION,
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
        raise SystemExit(f"provider live smoke failed safely: {error}") from None
    for label, value in summary.items():
        print(f"{label.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
