import re
from typing import Annotated
from uuid import UUID

from fastapi import Header, Request

from services.api.app.application.context import (
    ActorContext,
    OrganizationContext,
    TenantContext,
)
from services.api.app.application.errors import (
    InvalidRequest,
    ResourceNotFound,
    TemporaryIdentityDisabled,
)
from services.api.app.config import ApiSettings

ACTOR_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,199}$")

ActorHeader = Annotated[str | None, Header(alias="X-Actor-Subject")]
OrganizationHeader = Annotated[str | None, Header(alias="X-Organization-Id")]
WorkspaceHeader = Annotated[str | None, Header(alias="X-Workspace-Id")]


def require_actor_context(
    request: Request,
    x_actor_subject: ActorHeader = None,
    x_organization_id: OrganizationHeader = None,
    x_workspace_id: WorkspaceHeader = None,
) -> ActorContext:
    _require_temporary_context_enabled(request)
    if x_organization_id is not None or x_workspace_id is not None:
        raise InvalidRequest("bootstrap context must not include tenant headers")
    return ActorContext(
        actor_subject=_parse_actor_subject(x_actor_subject),
        correlation_id=request.state.correlation_id,
    )


def require_organization_context(
    request: Request,
    organization_id: UUID,
    x_actor_subject: ActorHeader = None,
    x_organization_id: OrganizationHeader = None,
    x_workspace_id: WorkspaceHeader = None,
) -> OrganizationContext:
    _require_temporary_context_enabled(request)
    if x_workspace_id is not None:
        raise ResourceNotFound("organization context is not accessible")
    header_organization_id = _parse_uuid(x_organization_id, "X-Organization-Id")
    if header_organization_id != organization_id:
        raise ResourceNotFound("organization context is not accessible")
    return OrganizationContext(
        actor_subject=_parse_actor_subject(x_actor_subject),
        correlation_id=request.state.correlation_id,
        organization_id=organization_id,
    )


def require_tenant_context(
    request: Request,
    organization_id: UUID,
    workspace_id: UUID,
    x_actor_subject: ActorHeader = None,
    x_organization_id: OrganizationHeader = None,
    x_workspace_id: WorkspaceHeader = None,
) -> TenantContext:
    _require_temporary_context_enabled(request)
    header_organization_id = _parse_uuid(x_organization_id, "X-Organization-Id")
    header_workspace_id = _parse_uuid(x_workspace_id, "X-Workspace-Id")
    if header_organization_id != organization_id or header_workspace_id != workspace_id:
        raise ResourceNotFound("tenant context is not accessible")
    return TenantContext(
        actor_subject=_parse_actor_subject(x_actor_subject),
        correlation_id=request.state.correlation_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )


def _require_temporary_context_enabled(request: Request) -> None:
    settings: ApiSettings = request.app.state.settings
    if not settings.temporary_identity_headers_enabled:
        raise TemporaryIdentityDisabled(
            "temporary identity headers are disabled in this environment"
        )


def _parse_actor_subject(value: str | None) -> str:
    if value is None or not ACTOR_PATTERN.fullmatch(value):
        raise InvalidRequest("X-Actor-Subject is required and invalid")
    return value


def _parse_uuid(value: str | None, header_name: str) -> UUID:
    if value is None:
        raise InvalidRequest(f"{header_name} is required")
    try:
        return UUID(value)
    except ValueError as error:
        raise InvalidRequest(f"{header_name} must be a UUID") from error
