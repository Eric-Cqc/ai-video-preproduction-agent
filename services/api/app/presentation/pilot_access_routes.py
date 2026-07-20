from typing import cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field

from services.api.app.application.pilot_access import (
    COOKIE_NAME,
    FailedAccessLimiter,
    issue_session,
    password_matches,
)
from services.api.app.config import ApiSettings

router = APIRouter(prefix="/api/v1", tags=["pilot-access"])


class PilotAccessRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class PilotContextResponse(BaseModel):
    actor_subject: str
    organization_id: str
    workspace_id: str


def _settings(request: Request) -> ApiSettings:
    return cast(ApiSettings, request.app.state.settings)


@router.post("/pilot-access", status_code=status.HTTP_204_NO_CONTENT)
def grant_pilot_access(payload: PilotAccessRequest, request: Request) -> Response:
    settings = _settings(request)
    if not settings.hosted_pilot_enabled:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    limiter = cast(FailedAccessLimiter, request.app.state.pilot_access_limiter)
    client_key = request.client.host if request.client is not None else "unknown"
    if not limiter.allowed(client_key) or not password_matches(
        payload.password, settings.pilot_access_password or ""
    ):
        limiter.record_failure(client_key)
        return Response(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
                if not limiter.allowed(client_key)
                else status.HTTP_401_UNAUTHORIZED
            )
        )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        COOKIE_NAME,
        issue_session(
            settings.pilot_session_secret or "", ttl_seconds=settings.pilot_session_ttl_seconds
        ),
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.pilot_session_ttl_seconds,
        path="/",
    )
    return response


@router.post("/pilot-access/logout", status_code=status.HTTP_204_NO_CONTENT)
def revoke_pilot_access() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/pilot-context", response_model=PilotContextResponse)
def pilot_context(request: Request) -> PilotContextResponse:
    settings = _settings(request)
    return PilotContextResponse(
        actor_subject=settings.pilot_actor_subject or "",
        organization_id=str(settings.pilot_organization_id),
        workspace_id=str(settings.pilot_workspace_id),
    )
