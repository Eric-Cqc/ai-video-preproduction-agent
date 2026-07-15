from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from services.api.app.application.context import (
    ActorContext,
    OrganizationContext,
    TenantContext,
)
from services.api.app.application.services import TenantApplicationService
from services.api.app.domain import MembershipRole
from services.api.app.presentation.context import (
    require_actor_context,
    require_organization_context,
    require_tenant_context,
)
from services.api.app.presentation.schemas import (
    AuditEventListResponse,
    AuditEventResponse,
    MembershipCreate,
    MembershipResponse,
    OrganizationCreate,
    OrganizationResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectPatch,
    ProjectResponse,
    ProjectTransition,
    WorkspaceCreate,
    WorkspaceResponse,
)

router = APIRouter(prefix="/api/v1", tags=["tenant-persistence"])

ActorDependency = Annotated[ActorContext, Depends(require_actor_context)]
OrganizationDependency = Annotated[OrganizationContext, Depends(require_organization_context)]
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> TenantApplicationService:
    return cast(TenantApplicationService, request.app.state.tenant_application_service)


ServiceDependency = Annotated[TenantApplicationService, Depends(get_service)]


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    payload: OrganizationCreate, context: ActorDependency, service: ServiceDependency
) -> OrganizationResponse:
    return OrganizationResponse.model_validate(
        service.create_organization(context, slug=payload.slug, name=payload.name)
    )


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    context: OrganizationDependency, service: ServiceDependency
) -> OrganizationResponse:
    return OrganizationResponse.model_validate(service.get_organization(context))


@router.post(
    "/organizations/{organization_id}/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    payload: WorkspaceCreate, context: OrganizationDependency, service: ServiceDependency
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(
        service.create_workspace(context, slug=payload.slug, name=payload.name)
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}",
    response_model=WorkspaceResponse,
)
def get_workspace(context: TenantDependency, service: ServiceDependency) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(service.get_workspace(context))


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership(
    payload: MembershipCreate, context: TenantDependency, service: ServiceDependency
) -> MembershipResponse:
    return MembershipResponse.model_validate(
        service.create_membership(
            context,
            actor_subject=payload.actor_subject,
            role=MembershipRole(payload.role),
        )
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate, context: TenantDependency, service: ServiceDependency
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        service.create_project(context, name=payload.name, description=payload.description)
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects",
    response_model=ProjectListResponse,
)
def list_projects(context: TenantDependency, service: ServiceDependency) -> ProjectListResponse:
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(item) for item in service.list_projects(context)]
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}",
    response_model=ProjectResponse,
)
def get_project(
    project_id: UUID, context: TenantDependency, service: ServiceDependency
) -> ProjectResponse:
    return ProjectResponse.model_validate(service.get_project(context, project_id))


@router.patch(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}",
    response_model=ProjectResponse,
)
def update_project(
    project_id: UUID,
    payload: ProjectPatch,
    context: TenantDependency,
    service: ServiceDependency,
) -> ProjectResponse:
    changed_fields = frozenset(payload.model_fields_set - {"expected_version"})
    return ProjectResponse.model_validate(
        service.update_project(
            context,
            project_id,
            expected_version=payload.expected_version,
            changed_fields=changed_fields,
            name=payload.name,
            description=payload.description,
        )
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/activate",
    response_model=ProjectResponse,
)
def activate_project(
    project_id: UUID,
    payload: ProjectTransition,
    context: TenantDependency,
    service: ServiceDependency,
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        service.activate_project(context, project_id, expected_version=payload.expected_version)
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/archive",
    response_model=ProjectResponse,
)
def archive_project(
    project_id: UUID,
    payload: ProjectTransition,
    context: TenantDependency,
    service: ServiceDependency,
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        service.archive_project(context, project_id, expected_version=payload.expected_version)
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/audit-events",
    response_model=AuditEventListResponse,
)
def list_project_audit_events(
    project_id: UUID, context: TenantDependency, service: ServiceDependency
) -> AuditEventListResponse:
    return AuditEventListResponse(
        items=[
            AuditEventResponse.model_validate(item)
            for item in service.list_project_audit_events(context, project_id)
        ]
    )
