from uuid import UUID

from fastapi.testclient import TestClient

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
