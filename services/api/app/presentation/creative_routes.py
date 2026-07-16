from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict

from services.api.app.application.context import TenantContext
from services.api.app.application.creative_services import CreativeApplicationService
from services.api.app.domain import CreativeConceptRun
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey

router = APIRouter(prefix="/api/v1", tags=["creative-foundation"])
Tenant = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> CreativeApplicationService:
    return cast(CreativeApplicationService, request.app.state.creative_application_service)


Service = Annotated[CreativeApplicationService, Depends(get_service)]


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _run(value: CreativeConceptRun) -> dict[str, object]:
    return {
        "id": value.id,
        "status": value.status,
        "brief_id": value.brief_id,
        "brief_version_id": value.brief_version_id,
        "created_at": value.created_at,
        "completed_at": value.completed_at,
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{brief_version_id}/concept-runs",
    status_code=201,
)
def generate(
    project_id: UUID,
    brief_id: UUID,
    brief_version_id: UUID,
    _: EmptyRequest,
    context: Tenant,
    idempotency_key: IdempotencyKey,
    service: Service,
    response: Response,
) -> dict[str, object]:
    result = service.generate_concepts(
        context, project_id, brief_id, brief_version_id, idempotency_key=idempotency_key
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {
        "run": _run(result.run),
        "candidates": [
            {
                "id": c.id,
                "candidate_index": c.candidate_index,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in result.candidates
        ],
        "replayed": result.replayed,
    }


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/concept-runs/{concept_run_id}"
)
def get_run(
    project_id: UUID, concept_run_id: UUID, context: Tenant, service: Service
) -> dict[str, object]:
    return _run(service.get_run(context, project_id, concept_run_id))


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/concept-runs/{concept_run_id}/candidates"
)
def list_candidates(
    project_id: UUID, concept_run_id: UUID, context: Tenant, service: Service
) -> dict[str, object]:
    return {
        "items": [
            {
                "id": c.id,
                "candidate_index": c.candidate_index,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in service.list_candidates(context, project_id, concept_run_id)
        ]
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/concept-runs/{concept_run_id}/candidates/{candidate_id}/select",
    status_code=201,
)
def select(
    project_id: UUID,
    concept_run_id: UUID,
    candidate_id: UUID,
    _: EmptyRequest,
    context: Tenant,
    idempotency_key: IdempotencyKey,
    service: Service,
    response: Response,
) -> dict[str, object]:
    result = service.select_concept(
        context, project_id, concept_run_id, candidate_id, idempotency_key=idempotency_key
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {
        "selection_id": result.selection.id,
        "candidate_id": result.selection.concept_candidate_id,
        "replayed": result.replayed,
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/concept-runs/{concept_run_id}/scripts",
    status_code=201,
)
def script(
    project_id: UUID,
    concept_run_id: UUID,
    _: EmptyRequest,
    context: Tenant,
    idempotency_key: IdempotencyKey,
    service: Service,
    response: Response,
) -> dict[str, object]:
    result = service.generate_script(
        context, project_id, concept_run_id, idempotency_key=idempotency_key
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {
        "script_version_id": result.version.id,
        "content": result.version.content,
        "replayed": result.replayed,
    }


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/scripts/{script_version_id}"
)
def get_script(
    project_id: UUID, script_version_id: UUID, context: Tenant, service: Service
) -> dict[str, object]:
    value = service.get_script(context, project_id, script_version_id)
    return {
        "id": value.id,
        "content": value.content,
        "brief_version_id": value.brief_version_id,
        "concept_candidate_id": value.concept_candidate_id,
        "concept_selection_id": value.concept_selection_id,
    }
