from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from services.api.app.application.candidate_review_services import (
    BriefCandidateReviewService,
    CandidateReviewResult,
)
from services.api.app.application.context import TenantContext
from services.api.app.presentation.candidate_review_schemas import (
    CandidateAcceptRequest,
    CandidateContentResponse,
    CandidateRejectRequest,
    CandidateReviewResponse,
    CandidateRunResponse,
)
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey

router = APIRouter(prefix="/api/v1", tags=["brief-candidate-review"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> BriefCandidateReviewService:
    return cast(BriefCandidateReviewService, request.app.state.brief_candidate_review_service)


ServiceDependency = Annotated[BriefCandidateReviewService, Depends(get_service)]


def _response(result: CandidateReviewResult) -> CandidateReviewResponse:
    review = result.review
    return CandidateReviewResponse(
        review_id=review.id,
        action=review.action,
        status=review.status,
        brief_id=review.brief_id,
        brief_version_id=review.brief_version_id,
        replayed=result.replayed,
        completed_at=review.completed_at,
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/brief-extraction-runs/{run_id}",
    response_model=CandidateRunResponse,
)
def get_run(
    project_id: UUID, run_id: UUID, context: TenantDependency, service: ServiceDependency
) -> CandidateRunResponse:
    run = service.get_run(context, project_id, run_id)
    return CandidateRunResponse(id=run.id, status=run.status.value, created_at=run.created_at)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/brief-extraction-runs/{run_id}/candidate",
    response_model=CandidateContentResponse,
)
def get_candidate(
    project_id: UUID, run_id: UUID, context: TenantDependency, service: ServiceDependency
) -> CandidateContentResponse:
    run = service.get_run(context, project_id, run_id)
    if run.candidate_structured_brief is None:
        from services.api.app.application.errors import ResourceNotFound

        raise ResourceNotFound("candidate is not accessible")
    return CandidateContentResponse(
        run_id=run.id,
        candidate=run.candidate_structured_brief,
        candidate_issues=run.candidate_issues,
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/brief-extraction-runs/{run_id}/accept",
    response_model=CandidateReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept(
    project_id: UUID,
    run_id: UUID,
    payload: CandidateAcceptRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> CandidateReviewResponse:
    result = service.accept(
        context,
        project_id,
        run_id,
        idempotency_key=idempotency_key,
        brief_id=payload.brief_id,
        expected_brief_version=payload.expected_brief_version,
        expected_current_version_id=payload.expected_current_version_id,
        accepted_content=payload.accepted_content,
        title=payload.title,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _response(result)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/brief-extraction-runs/{run_id}/reject",
    response_model=CandidateReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def reject(
    project_id: UUID,
    run_id: UUID,
    payload: CandidateRejectRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> CandidateReviewResponse:
    result = service.reject(
        context,
        project_id,
        run_id,
        idempotency_key=idempotency_key,
        reason=payload.reason,
        note=payload.note,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _response(result)
