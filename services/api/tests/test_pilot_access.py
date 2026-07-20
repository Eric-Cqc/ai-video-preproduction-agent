from uuid import UUID

from fastapi.testclient import TestClient

from services.api.app.application.pilot_access import issue_session, session_is_valid
from services.api.app.config import ApiSettings
from services.api.app.main import create_app


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


def test_failed_attempt_limit_isolated_by_forwarded_client_address() -> None:
    with TestClient(create_app(_settings()), base_url="https://pilot.example.test") as client:
        for _ in range(5):
            limited = client.post(
                "/api/v1/pilot-access",
                json={"password": "incorrect"},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
        assert limited.status_code == 429

        still_limited = client.post(
            "/api/v1/pilot-access",
            json={"password": "private-pilot-password"},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        granted = client.post(
            "/api/v1/pilot-access",
            json={"password": "private-pilot-password"},
            headers={"X-Forwarded-For": "203.0.113.11"},
        )

        assert still_limited.status_code == 429
        assert granted.status_code == 204
        assert client.get("/api/v1/pilot-context").status_code == 200


def test_pilot_access_errors_are_safe_and_actionable() -> None:
    with TestClient(create_app(_settings()), base_url="https://pilot.example.test") as client:
        rejected = client.post("/api/v1/pilot-access", json={"password": "incorrect"})
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "pilot_access_invalid_credential"
        assert "private-pilot-password" not in rejected.text

        for _ in range(4):
            limited = client.post("/api/v1/pilot-access", json={"password": "incorrect"})
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "pilot_access_rate_limited"
        assert limited.headers["retry-after"] == "300"


def test_pilot_session_expires_at_its_expiry_boundary() -> None:
    token = issue_session("x" * 32, ttl_seconds=300, now=1_000)

    assert session_is_valid(token, "x" * 32, now=1_299)
    assert not session_is_valid(token, "x" * 32, now=1_300)
