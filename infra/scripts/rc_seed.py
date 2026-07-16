import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    encoded = json.dumps(body).encode() if body is not None else None
    request = Request(
        url,
        data=encoded,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urlopen(request, timeout=5) as response:  # noqa: S310 -- fixed local API origin
        return json.loads(response.read())


def main() -> None:
    if os.environ.get("APP_ENVIRONMENT", "local") not in {"local", "test"}:
        raise SystemExit("rc-seed is restricted to local/test")
    base = os.environ.get("API_BASE_URL", "http://127.0.0.1:18000").rstrip("/")
    if base not in {"http://127.0.0.1:18000", "http://localhost:18000"}:
        raise SystemExit("rc-seed requires the approved local API origin")
    state_path = Path(".local/rc/context.json")
    if state_path.exists():
        state = json.loads(state_path.read_text())
        _request(
            f"{base}/api/v1/organizations/{state['organization_id']}",
            headers={
                "X-Actor-Subject": state["actor"],
                "X-Organization-Id": state["organization_id"],
            },
        )
        print("RC context already ready")
        return
    actor = "actor:local-rc-owner"
    organization = _request(
        f"{base}/api/v1/organizations",
        method="POST",
        body={"slug": "local-rc", "name": "Local RC"},
        headers={"X-Actor-Subject": actor},
    )
    organization_id = str(organization["id"])
    workspace = _request(
        f"{base}/api/v1/organizations/{organization_id}/workspaces",
        method="POST",
        body={"slug": "production", "name": "Production Desk"},
        headers={"X-Actor-Subject": actor, "X-Organization-Id": organization_id},
    )
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "actor": actor,
                "organization_id": organization_id,
                "workspace_id": str(workspace["id"]),
            },
            sort_keys=True,
        )
    )
    print("RC context created")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"rc-seed failed with HTTP {error.code}") from None
