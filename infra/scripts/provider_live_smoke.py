"""Explicit, non-CI DeepSeek smoke; prints no key, prompt, or response."""

import os

from services.api.app.application.model_provider import (
    DeepSeekProvider,
    ModelRequest,
    ProviderOutcomeStatus,
)
from services.api.app.config import ApiSettings


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
        max_input_bytes=1024,
        max_output_bytes=4096,
    )
    outcome = provider.complete(
        ModelRequest("live_smoke", "1", "Return exactly one JSON object: {}", "{}", 128)
    )
    if outcome.status is not ProviderOutcomeStatus.SUCCESS:
        raise SystemExit(f"provider live smoke failed safely: {outcome.status.value}")
    print("provider live smoke succeeded; response body was not printed")


if __name__ == "__main__":
    main()
