"""Bounded hosted-stack smoke; real provider use remains separately opt-in."""

import os
from urllib.request import urlopen


def main() -> None:
    base_url = os.environ.get("HOSTED_API_URL", "http://api:8000").rstrip("/")
    with urlopen(f"{base_url}/api/v1/health", timeout=5) as response:  # noqa: S310 -- fixed internal URL
        if response.status != 200:
            raise SystemExit("hosted API health check failed")
    if (
        os.environ.get("MODEL_PROVIDER") == "deepseek"
        and os.environ.get("ALLOW_PROVIDER_LIVE_SMOKE") != "1"
    ):
        print("Hosted smoke passed; real DeepSeek smoke remains explicitly disabled")
        return
    print("Hosted smoke passed")


if __name__ == "__main__":
    main()
