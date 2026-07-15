from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from foundation_contracts import validate_health_response

from services.api.app.config import ApiSettings
from services.api.app.main import create_app


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    app = create_app(ApiSettings(app_environment="test"))
    with TestClient(app) as client:
        yield client


def test_versioned_health_endpoint_matches_contract(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    validate_health_response(response.json())
    assert response.json()["service"] == "foundation-api"
    assert response.json()["environment"] == "test"


def test_root_route_redirects_to_versioned_health(api_client: TestClient) -> None:
    response = api_client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/health"


def test_unhandled_errors_do_not_expose_stack_traces(monkeypatch: pytest.MonkeyPatch) -> None:
    from services.api.app.routes import health as health_module

    def fail(_: ApiSettings) -> None:
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(health_module, "build_health_response", fail)
    app = create_app(ApiSettings(app_environment="test"))
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/v1/health")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "sensitive internal detail" not in response.text
