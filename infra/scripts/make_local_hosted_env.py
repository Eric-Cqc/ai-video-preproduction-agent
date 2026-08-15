"""Create a non-production hosted Compose environment without overwriting an existing file."""

from __future__ import annotations

import secrets
from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _replacement_values() -> dict[str, str]:
    return {
        "APP_ENVIRONMENT": "hosted",
        "PILOT_DOMAIN": "localhost",
        "API_BASE_URL": "http://api:8000",
        "PUBLIC_API_BASE_URL": "https://localhost/api",
        "API_ALLOWED_CORS_ORIGINS": "https://localhost",
        "MODEL_PROVIDER": "deterministic_offline",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "PILOT_ACCESS_PASSWORD": secrets.token_urlsafe(32),
        "PILOT_SESSION_SECRET": secrets.token_urlsafe(48),
    }


def _render(template: str, replacements: dict[str, str]) -> str:
    lines = template.splitlines(keepends=True)
    seen: set[str] = set()
    rendered: list[str] = []
    for line in lines:
        key, separator, _ = line.partition("=")
        if separator and key in replacements:
            newline = "\n" if line.endswith("\n") else ""
            rendered.append(f"{key}={replacements[key]}{newline}")
            seen.add(key)
        else:
            rendered.append(line)
    missing = sorted(set(replacements) - seen)
    if missing:
        raise RuntimeError("hosted environment template is missing required settings")
    return "".join(rendered)


def main() -> int:
    root = _repository_root()
    target = root / ".env.hosted"
    template_path = root / ".env.hosted.example"
    if target.exists():
        raise SystemExit(".env.hosted already exists; refusing to overwrite it")
    try:
        template = template_path.read_text(encoding="utf-8")
        rendered = _render(template, _replacement_values())
        with target.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
        target.chmod(0o600)
    except FileExistsError:
        raise SystemExit(".env.hosted was created concurrently; refusing to overwrite it") from None
    except OSError as error:
        raise SystemExit("could not create .env.hosted") from error

    print("Created .env.hosted for local hosted validation.")
    print("Run: make hosted-build && make hosted-up && make hosted-bootstrap && make hosted-smoke")
    print(
        "Smoke TLS settings: HOSTED_SMOKE_CA_BUNDLE may name a CA bundle visible inside the api "
        "container; for localhost only, set HOSTED_SMOKE_INSECURE=1 if the Caddy CA is unavailable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
