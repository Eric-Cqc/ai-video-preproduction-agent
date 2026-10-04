from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from services.api.app.application.brief_services import BriefBundle
from services.api.app.application.context import TenantContext
from services.api.app.application.idea_intake_services import IdeaIntakeApplicationService
from services.api.app.presentation.brief_routes import _bundle
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.idea_intake_schemas import (
    IdeaIntakeConfirm,
    IdeaIntakeConfirmationResponse,
    IdeaIntakeCreate,
    IdeaIntakeListResponse,
    IdeaIntakePatch,
    IdeaIntakeResponse,
)

router = APIRouter(prefix="/api/v1", tags=["idea-intake"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> IdeaIntakeApplicationService:
    return cast(IdeaIntakeApplicationService, request.app.state.idea_intake_service)


ServiceDependency = Annotated[IdeaIntakeApplicationService, Depends(get_service)]


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/idea-intakes",
    response_model=IdeaIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_idea_intake(
    project_id: UUID,
    payload: IdeaIntakeCreate,
    context: TenantDependency,
    service: ServiceDependency,
) -> IdeaIntakeResponse:
    return IdeaIntakeResponse.model_validate(
        service.create(context, project_id, raw_idea=payload.idea)
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/idea-intakes",
    response_model=IdeaIntakeListResponse,
)
def list_idea_intakes(
    project_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> IdeaIntakeListResponse:
    return IdeaIntakeListResponse(
        items=[
            IdeaIntakeResponse.model_validate(item)
            for item in service.list_intakes(context, project_id)
        ]
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/idea-intakes/{idea_intake_id}",
    response_model=IdeaIntakeResponse,
)
def get_idea_intake(
    project_id: UUID,
    idea_intake_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> IdeaIntakeResponse:
    return IdeaIntakeResponse.model_validate(service.get(context, project_id, idea_intake_id))


@router.patch(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/idea-intakes/{idea_intake_id}",
    response_model=IdeaIntakeResponse,
)
def update_idea_intake(
    project_id: UUID,
    idea_intake_id: UUID,
    payload: IdeaIntakePatch,
    context: TenantDependency,
    service: ServiceDependency,
) -> IdeaIntakeResponse:
    return IdeaIntakeResponse.model_validate(
        service.update(
            context,
            project_id,
            idea_intake_id,
            expected_version=payload.expected_version,
            objective=payload.objective,
            platform=payload.platform,
            audience=payload.audience,
            duration_seconds=payload.duration_seconds,
            content_type=payload.content_type,
            tone=payload.tone,
            key_messages=payload.key_messages,
            call_to_action=payload.call_to_action,
            constraints=payload.constraints,
            must_include=payload.must_include,
            must_avoid=payload.must_avoid,
            assumptions=payload.assumptions,
            missing_fields=payload.missing_fields,
        )
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/idea-intakes/{idea_intake_id}/confirm",
    response_model=IdeaIntakeConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_idea_intake(
    project_id: UUID,
    idea_intake_id: UUID,
    payload: IdeaIntakeConfirm,
    context: TenantDependency,
    service: ServiceDependency,
) -> IdeaIntakeConfirmationResponse:
    result = service.confirm(
        context,
        project_id,
        idea_intake_id,
        expected_version=payload.expected_version,
        title=payload.title,
    )
    return IdeaIntakeConfirmationResponse(
        idea_intake=IdeaIntakeResponse.model_validate(result.intake),
        result=_bundle(BriefBundle(result.brief, result.current_version, result.issues)),
    )
