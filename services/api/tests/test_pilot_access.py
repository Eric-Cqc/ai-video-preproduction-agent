from types import SimpleNamespace
from typing import cast
from uuid import UUID

from fastapi.testclient import TestClient
from starlette.requests import Request

from services.api.app.application.pilot_access import FailedAccessLimiter
from services.api.app.config import ApiSettings
from services.api.app.main import create_app
from services.api.app.presentation.pilot_access_routes import (
    PilotAccessRequest,
    _client_key,
    grant_pilot_access,
)


def _settings() -> ApiSettings:
    return ApiSettings(
        app_environment="hosted_test",
        database_url="postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test",
        api_allowed_cors_origins="https://pilot.example.test",
        pilot_access_password="private-pilot-password",
        pilot_session_secret="x" * 32,
        pilot_organization_id=UUID("11111111-1111-1111-1111-111111111111"),
        pilot_workspace_id=UUID("22222222-2222-2222-2222-222222222222"),
        pilot_actor_subject="pilot:owner",
    )


def test_hosted_pilot_access_gate_uses_secure_cookie_and_fixed_context() -> None:
    with TestClient(create_app(_settings()), base_url="https://pilot.example.test") as client:
        assert client.get("/api/v1/pilot-context").status_code == 401
        assert (
            client.post("/api/v1/pilot-access", json={"password": "incorrect"}).status_code == 401
        )
        granted = client.post("/api/v1/pilot-access", json={"password": "private-pilot-password"})
        assert granted.status_code == 204
        assert "httponly" in granted.headers["set-cookie"].lower()
        assert "secure" in granted.headers["set-cookie"].lower()
        context = client.get("/api/v1/pilot-context")
        assert context.status_code == 200
        assert context.json() == {
            "actor_subject": "pilot:owner",
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "workspace_id": "22222222-2222-2222-2222-222222222222",
        }
        assert client.post("/api/v1/pilot-access/logout").status_code == 204
        assert client.get("/api/v1/pilot-context").status_code == 401


def test_hosted_pilot_access_limits_failed_attempts() -> None:
    with TestClient(create_app(_settings()), base_url="https://pilot.example.test") as client:
        for _ in range(4):
            assert (
                client.post("/api/v1/pilot-access", json={"password": "incorrect"}).status_code
                == 401
            )
        assert (
            client.post("/api/v1/pilot-access", json={"password": "incorrect"}).status_code == 429
        )


def _fake_request(
    settings: ApiSettings,
    *,
    socket_host: str = "10.0.0.8",
    forwarded_for: str | None = None,
    limiter: FailedAccessLimiter | None = None,
) -> Request:
    headers = {} if forwarded_for is None else {"x-forwarded-for": forwarded_for}
    return cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=settings,
                    pilot_access_limiter=limiter or FailedAccessLimiter(),
                )
            ),
            client=SimpleNamespace(host=socket_host),
            headers=headers,
        ),
    )


def test_hosted_client_key_uses_first_xff_hop_and_local_ignores_it() -> None:
    hosted = _settings()
    local = ApiSettings(
        app_environment="local",
        database_url="postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test",
    )
    hosted_request = _fake_request(
        hosted,
        socket_host="172.18.0.4",
        forwarded_for="198.51.100.7, 172.18.0.1",
    )
    local_request = _fake_request(
        local,
        socket_host="127.0.0.1",
        forwarded_for="198.51.100.7, 127.0.0.1",
    )
    missing_request = _fake_request(hosted, socket_host="172.18.0.4")

    assert _client_key(hosted_request, hosted) == "198.51.100.7"
    assert _client_key(local_request, local) == "127.0.0.1"
    assert _client_key(missing_request, hosted) == "172.18.0.4"


def test_hosted_limiter_isolates_forwarded_clients() -> None:
    settings = _settings()
    limiter = FailedAccessLimiter(max_attempts=2)

    first_client = _fake_request(settings, forwarded_for="198.51.100.10", limiter=limiter)
    second_client = _fake_request(settings, forwarded_for="198.51.100.11", limiter=limiter)
    assert (
        grant_pilot_access(PilotAccessRequest(password="incorrect"), first_client).status_code
        == 401
    )
    assert (
        grant_pilot_access(PilotAccessRequest(password="incorrect"), second_client).status_code
        == 401
    )
    assert (
        grant_pilot_access(PilotAccessRequest(password="incorrect"), first_client).status_code
        == 429
    )
    assert (
        grant_pilot_access(PilotAccessRequest(password="incorrect"), second_client).status_code
        == 429
    )
