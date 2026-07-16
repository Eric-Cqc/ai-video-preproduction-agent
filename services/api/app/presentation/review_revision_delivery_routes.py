from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from services.api.app.application.context import TenantContext
from services.api.app.application.review_revision_delivery_services import (
    ReviewRevisionDeliveryApplicationService,
)
from services.api.app.domain import (
    DeliveryPackageVersion,
    PlanningReview,
    PlanningReviewOutcome,
    PlanningRevisionRequest,
    ReviewArtifactType,
)
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey
from services.api.app.presentation.review_revision_delivery_schemas import (
    DeliveryExportCreateRequest,
    DeliveryPackageCreateRequest,
    PlanningReviewSubmitRequest,
    RevisionCompleteRequest,
)

router = APIRouter(prefix="/api/v1", tags=["review-revision-delivery"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> ReviewRevisionDeliveryApplicationService:
    return cast(
        ReviewRevisionDeliveryApplicationService, request.app.state.review_revision_delivery_service
    )


ServiceDependency = Annotated[ReviewRevisionDeliveryApplicationService, Depends(get_service)]


def _review(value: PlanningReview) -> dict[str, object]:
    return {
        "id": value.id,
        "artifact_type": value.artifact_type,
        "script_version_id": value.script_version_id,
        "storyboard_version_id": value.storyboard_version_id,
        "shot_plan_version_id": value.shot_plan_version_id,
        "review_round": value.review_round,
        "outcome": value.outcome,
        "summary": value.summary,
        "requested_changes": value.requested_changes,
        "reviewed_by_actor_subject": value.reviewed_by_actor_subject,
        "reviewed_at": value.reviewed_at,
        "created_at": value.created_at,
    }


def _revision(value: PlanningRevisionRequest) -> dict[str, object]:
    return {
        "id": value.id,
        "review_id": value.review_id,
        "artifact_type": value.artifact_type,
        "source_script_version_id": value.source_script_version_id,
        "source_storyboard_version_id": value.source_storyboard_version_id,
        "source_shot_plan_version_id": value.source_shot_plan_version_id,
        "status": value.status,
        "created_at": value.created_at,
        "completed_at": value.completed_at,
        "successor_script_version_id": value.successor_script_version_id,
        "successor_storyboard_version_id": value.successor_storyboard_version_id,
        "successor_shot_plan_version_id": value.successor_shot_plan_version_id,
    }


def _package(package: DeliveryPackageVersion) -> dict[str, object]:
    return {
        "id": package.id,
        "delivery_package_id": package.delivery_package_id,
        "version_number": package.version_number,
        "script_version_id": package.script_version_id,
        "storyboard_version_id": package.storyboard_version_id,
        "shot_plan_version_id": package.shot_plan_version_id,
        "approval_review_id": package.approval_review_id,
        "manifest_schema_version": package.manifest_schema_version,
        "manifest": package.manifest,
        "manifest_digest": package.manifest_digest,
        "created_at": package.created_at,
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/planning-reviews",
    status_code=status.HTTP_201_CREATED,
)
def submit_review(
    project_id: UUID,
    payload: PlanningReviewSubmitRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    result = service.submit_review(
        context,
        project_id,
        artifact_type=ReviewArtifactType(payload.artifact_type),
        script_version_id=payload.script_version_id,
        storyboard_version_id=payload.storyboard_version_id,
        shot_plan_version_id=payload.shot_plan_version_id,
        outcome=PlanningReviewOutcome(payload.outcome),
        summary=payload.summary,
        requested_changes=payload.requested_changes,
        idempotency_key=idempotency_key,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {
        "review": _review(result.review),
        "revision_request": _revision(result.revision_request) if result.revision_request else None,
        "replayed": result.replayed,
    }


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/planning-reviews/{review_id}"
)
def get_review(
    project_id: UUID, review_id: UUID, context: TenantDependency, service: ServiceDependency
) -> dict[str, object]:
    return {"review": _review(service.get_review(context, project_id, review_id))}


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/planning-reviews"
)
def list_reviews(
    project_id: UUID, context: TenantDependency, service: ServiceDependency
) -> dict[str, object]:
    return {"items": [_review(value) for value in service.list_reviews(context, project_id)]}


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/revision-requests/{revision_request_id}"
)
def get_revision(
    project_id: UUID,
    revision_request_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    return {
        "revision_request": _revision(
            service.get_revision_request(context, project_id, revision_request_id)
        )
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/revision-requests/{revision_request_id}/complete",
    status_code=status.HTTP_201_CREATED,
)
def complete_revision(
    project_id: UUID,
    revision_request_id: UUID,
    payload: RevisionCompleteRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    result = service.complete_revision(
        context,
        project_id,
        revision_request_id,
        provider_mode=payload.provider_mode,
        idempotency_key=idempotency_key,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {
        "revision_request": _revision(result.request),
        "successor_script_version_id": result.successor_script_version_id,
        "successor_storyboard_version_id": result.successor_storyboard_version_id,
        "successor_shot_plan_version_id": result.successor_shot_plan_version_id,
        "replayed": result.replayed,
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/revision-requests/{revision_request_id}/cancel",
    status_code=status.HTTP_201_CREATED,
)
def cancel_revision(
    project_id: UUID,
    revision_request_id: UUID,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    return {
        "revision_request": _revision(
            service.cancel_revision(
                context, project_id, revision_request_id, idempotency_key=idempotency_key
            )
        )
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/delivery-packages",
    status_code=status.HTTP_201_CREATED,
)
def create_package(
    project_id: UUID,
    payload: DeliveryPackageCreateRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    result = service.create_delivery_package(
        context,
        project_id,
        script_version_id=payload.script_version_id,
        storyboard_version_id=payload.storyboard_version_id,
        shot_plan_version_id=payload.shot_plan_version_id,
        approval_review_id=payload.approval_review_id,
        idempotency_key=idempotency_key,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {"package": _package(result.version), "replayed": result.replayed}


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/delivery-packages/{delivery_package_version_id}"
)
def get_package(
    project_id: UUID,
    delivery_package_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    return {
        "package": _package(
            service.get_delivery_package(context, project_id, delivery_package_version_id)
        )
    }


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/delivery-packages/{delivery_package_version_id}/exports",
    status_code=status.HTTP_201_CREATED,
)
def export_package(
    project_id: UUID,
    delivery_package_version_id: UUID,
    payload: DeliveryExportCreateRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> dict[str, object]:
    result = service.export_delivery_package(
        context,
        project_id,
        delivery_package_version_id,
        export_format=payload.format,
        idempotency_key=idempotency_key,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return {
        "export": {
            "id": result.file.id,
            "format": result.file.format,
            "filename": result.file.filename,
            "checksum": result.file.checksum,
            "byte_size": result.file.byte_size,
            "created_at": result.file.created_at,
        },
        "replayed": result.replayed,
    }


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/delivery-packages/{delivery_package_version_id}/exports"
)
def list_exports(
    project_id: UUID,
    delivery_package_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    return {
        "items": [
            {
                "id": item.id,
                "format": item.format,
                "filename": item.filename,
                "checksum": item.checksum,
                "byte_size": item.byte_size,
                "created_at": item.created_at,
            }
            for item in service.list_exports(context, project_id, delivery_package_version_id)
        ]
    }


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/delivery-exports/{export_file_id}"
)
def download_export(
    project_id: UUID, export_file_id: UUID, context: TenantDependency, service: ServiceDependency
) -> StreamingResponse:
    export, chunks = service.read_export(context, project_id, export_file_id)
    return StreamingResponse(
        chunks,
        media_type=_content_type(export.format),
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


def _content_type(export_format: str) -> str:
    if export_format.endswith(".csv"):
        return "text/csv; charset=utf-8"
    if export_format.endswith(".zip"):
        return "application/zip"
    if export_format.endswith(".txt"):
        return "text/plain; charset=utf-8"
    return "application/json"
