from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import InvalidRequest
from services.api.app.application.source_object_services import (
    SourceObjectApplicationService,
    SourceObjectUploadResult,
)
from services.api.app.domain import SourceObject
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey
from services.api.app.presentation.source_asset_schemas import (
    SourceObjectResponse,
    SourceObjectUploadResponse,
)

router = APIRouter(prefix="/api/v1", tags=["source-objects"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> SourceObjectApplicationService:
    return cast(SourceObjectApplicationService, request.app.state.source_object_application_service)


ServiceDependency = Annotated[SourceObjectApplicationService, Depends(get_service)]


def _object(value: SourceObject) -> SourceObjectResponse:
    return SourceObjectResponse(
        id=value.id,
        source_asset_id=value.source_asset_id,
        source_asset_version_id=value.source_asset_version_id,
        state=value.state.value,
        observed_byte_size=value.observed_byte_size,
        created_at=value.created_at,
    )


def _upload_response(result: SourceObjectUploadResult) -> SourceObjectUploadResponse:
    if result.upload.completed_at is None:
        raise RuntimeError("accepted upload has no completion time")
    return SourceObjectUploadResponse(
        source_object=_object(result.source_object),
        replayed=result.replayed,
        completed_at=result.upload.completed_at,
        correlation_id=result.upload.correlation_id,
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    "/source-assets/{source_asset_id}/versions/{source_asset_version_id}/uploads",
    response_model=SourceObjectUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source_object(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    request: Request,
    response: Response,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
) -> SourceObjectUploadResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/octet-stream":
        raise InvalidRequest("Content-Type must be application/octet-stream")
    result = await service.upload(
        context,
        project_id,
        source_asset_id,
        source_asset_version_id,
        idempotency_key=idempotency_key,
        chunks=request.stream(),
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _upload_response(result)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    "/source-assets/{source_asset_id}/versions/{source_asset_version_id}/object",
    response_model=SourceObjectResponse,
)
def get_source_object(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> SourceObjectResponse:
    return _object(service.get(context, project_id, source_asset_id, source_asset_version_id))


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    "/source-assets/{source_asset_id}/versions/{source_asset_version_id}/object/content",
    response_class=StreamingResponse,
)
def read_source_object(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> StreamingResponse:
    _, chunks = service.read(context, project_id, source_asset_id, source_asset_version_id)
    return StreamingResponse(chunks, media_type="application/octet-stream")
