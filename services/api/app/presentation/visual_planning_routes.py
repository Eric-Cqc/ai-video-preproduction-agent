from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from services.api.app.application.context import TenantContext
from services.api.app.application.visual_planning_services import VisualPlanningApplicationService
from services.api.app.domain import ShotPlanRun, ShotPlanVersion, StoryboardRun, StoryboardVersion
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey
from services.api.app.presentation.visual_planning_schemas import (
    ShotPlanGenerationRequest,
    StoryboardGenerationRequest,
)

router = APIRouter(prefix="/api/v1", tags=["visual-planning"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> VisualPlanningApplicationService:
    return cast(
        VisualPlanningApplicationService, request.app.state.visual_planning_application_service
    )


ServiceDependency = Annotated[VisualPlanningApplicationService, Depends(get_service)]


def _run(value: StoryboardRun | ShotPlanRun) -> dict[str, object]:
    return {
        "id": value.id,
        "status": value.status,
        "created_at": value.created_at,
        "completed_at": value.completed_at,
        "brief_id": value.brief_id,
        "script_version_id": value.script_version_id,
        "brief_version_id": value.brief_version_id,
        "concept_run_id": value.concept_run_id,
        "concept_candidate_id": value.concept_candidate_id,
        "concept_selection_id": value.concept_selection_id,
        "script_run_id": value.script_run_id,
        "storyboard_run_id": getattr(value, "storyboard_run_id", None),
        "storyboard_version_id": getattr(value, "storyboard_version_id", None),
    }


def _version(value: StoryboardVersion | ShotPlanVersion) -> dict[str, object]:
    result: dict[str, object] = {
        "id": value.id,
        "storyboard_run_id": value.storyboard_run_id,
        "storyboard_version_id": getattr(value, "storyboard_version_id", None),
        "shot_plan_run_id": getattr(value, "shot_plan_run_id", None),
        "brief_id": value.brief_id,
        "brief_version_id": value.brief_version_id,
        "concept_run_id": value.concept_run_id,
        "concept_candidate_id": value.concept_candidate_id,
        "concept_selection_id": value.concept_selection_id,
        "script_run_id": value.script_run_id,
        "script_version_id": value.script_version_id,
        "version_number": value.version_number,
        "schema_version": value.schema_version,
        "content": value.content,
        "content_digest": None,
        "total_duration_seconds": value.total_duration_seconds,
        "scene_count": value.scene_count,
        "created_at": value.created_at,
    }
    if isinstance(value, ShotPlanVersion):
        result["shot_count"] = value.shot_count
    # Keep internal request/content digests out of the public response.
    result.pop("content_digest", None)
    return result


def _result(
    run: StoryboardRun | ShotPlanRun, version: StoryboardVersion | ShotPlanVersion, replayed: bool
) -> dict[str, object]:
    return {"run": _run(run), "version": _version(version), "replayed": replayed}


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/scripts/{script_version_id}/storyboards",
    status_code=status.HTTP_201_CREATED,
)
def generate_storyboard(
    project_id: UUID,
    script_version_id: UUID,
    payload: StoryboardGenerationRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    result = service.generate_storyboard(
        context,
        project_id,
        script_version_id,
        idempotency_key=idempotency_key,
        provider_mode=payload.provider_mode,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _result(result.run, result.version, result.replayed)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/storyboard-runs/{storyboard_run_id}"
)
def get_storyboard_run(
    project_id: UUID, storyboard_run_id: UUID, context: TenantDependency, service: ServiceDependency
) -> dict[str, object]:
    return {"run": _run(service.get_storyboard_run(context, project_id, storyboard_run_id))}


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/storyboards/{storyboard_version_id}"
)
def get_storyboard_version(
    project_id: UUID,
    storyboard_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    return {
        "version": _version(
            service.get_storyboard_version(context, project_id, storyboard_version_id)
        )
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/storyboards/{storyboard_version_id}/shot-plans",
    status_code=status.HTTP_201_CREATED,
)
def generate_shot_plan(
    project_id: UUID,
    storyboard_version_id: UUID,
    payload: ShotPlanGenerationRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    result = service.generate_shot_plan(
        context,
        project_id,
        storyboard_version_id,
        idempotency_key=idempotency_key,
        provider_mode=payload.provider_mode,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _result(result.run, result.version, result.replayed)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/shot-plan-runs/{shot_plan_run_id}"
)
def get_shot_plan_run(
    project_id: UUID, shot_plan_run_id: UUID, context: TenantDependency, service: ServiceDependency
) -> dict[str, object]:
    return {"run": _run(service.get_shot_plan_run(context, project_id, shot_plan_run_id))}


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/shot-plans/{shot_plan_version_id}"
)
def get_shot_plan_version(
    project_id: UUID,
    shot_plan_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    return {
        "version": _version(
            service.get_shot_plan_version(context, project_id, shot_plan_version_id)
        )
    }
