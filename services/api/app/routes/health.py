from datetime import UTC, datetime

from fastapi import APIRouter, Request
from foundation_contracts import HEALTH_CONTRACT_VERSION, validate_health_response

from services.api.app.config import ApiSettings
from services.api.app.metadata import SERVICE_NAME, SERVICE_VERSION
from services.api.app.models import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["foundation"])


def build_health_response(settings: ApiSettings) -> HealthResponse:
    payload = {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "environment": settings.app_environment,
        "contract_version": HEALTH_CONTRACT_VERSION,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    validate_health_response(payload)
    return HealthResponse.model_validate(payload)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings: ApiSettings = request.app.state.settings
    return build_health_response(settings)
