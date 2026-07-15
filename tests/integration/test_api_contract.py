from fastapi.testclient import TestClient
from foundation_contracts import validate_health_response

from services.api.app.config import ApiSettings
from services.api.app.main import create_app


def test_api_boundary_emits_the_canonical_health_contract() -> None:
    app = create_app(ApiSettings(app_environment="integration"))
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    validate_health_response(response.json())
    assert response.json()["contract_version"] == "1.0.0"
