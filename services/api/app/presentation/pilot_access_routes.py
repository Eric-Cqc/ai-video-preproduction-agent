import logging
from ipaddress import ip_address
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from services.api.app.application.pilot_access import (
    COOKIE_NAME,
    FailedAccessLimiter,
    issue_session,
    password_matches,
)
from services.api.app.config import ApiSettings

router = APIRouter(prefix="/api/v1", tags=["pilot-access"])
logger = logging.getLogger(__name__)


class PilotAccessRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class PilotContextResponse(BaseModel):
    actor_subject: str
    organization_id: str
    workspace_id: str


def _settings(request: Request) -> ApiSettings:
    return cast(ApiSettings, request.app.state.settings)


def _client_key(request: Request, settings: ApiSettings) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if settings.hosted_pilot_enabled and forwarded_for:
        candidate = forwarded_for.split(",", maxsplit=1)[0].strip()
        try:
            return f"forwarded:{ip_address(candidate).compressed}"
        except ValueError:
            pass
    peer = request.client.host if request.client is not None else "unknown"
    return f"peer:{peer}"


def _access_error(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    retry_after: int | None = None,
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    headers = {"X-Correlation-Id": correlation_id}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
            }
        },
        headers=headers,
    )


@router.post("/pilot-access", status_code=status.HTTP_204_NO_CONTENT)
def grant_pilot_access(payload: PilotAccessRequest, request: Request) -> Response:
    settings = _settings(request)
    if not settings.hosted_pilot_enabled:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    limiter = cast(FailedAccessLimiter, request.app.state.pilot_access_limiter)
    client_key = _client_key(request, settings)
    password_valid = password_matches(payload.password, settings.pilot_access_password or "")
    if not limiter.allowed(client_key):
        logger.warning("pilot access rate limited", extra={"event": "pilot_access.rate_limited"})
        return _access_error(
            request,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "pilot_access_rate_limited",
            "Too many access attempts",
            retry_after=limiter.window_seconds,
        )
    if not password_valid:
        limiter.record_failure(client_key)
        if not limiter.allowed(client_key):
            logger.warning(
                "pilot access rate limited", extra={"event": "pilot_access.rate_limited"}
            )
            return _access_error(
                request,
                status.HTTP_429_TOO_MANY_REQUESTS,
                "pilot_access_rate_limited",
                "Too many access attempts",
                retry_after=limiter.window_seconds,
            )
        logger.info("pilot access rejected", extra={"event": "pilot_access.rejected"})
        return _access_error(
            request,
            status.HTTP_401_UNAUTHORIZED,
            "pilot_access_invalid_credential",
            "Access credential is invalid",
        )
    limiter.reset(client_key)
    logger.info("pilot access granted", extra={"event": "pilot_access.granted"})
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
