from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from services.api.app.application.context import TenantContext
from services.api.app.application.document_extraction_services import (
    DocumentExtractionApplicationService,
    DocumentExtractionResult,
)
from services.api.app.domain import DocumentExtraction
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey
from services.api.app.presentation.source_asset_schemas import (
    DocumentExtractionMutationResponse,
    DocumentExtractionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["document-extractions"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> DocumentExtractionApplicationService:
    return cast(
        DocumentExtractionApplicationService,
        request.app.state.document_extraction_application_service,
    )


ServiceDependency = Annotated[DocumentExtractionApplicationService, Depends(get_service)]


def _extraction(value: DocumentExtraction) -> DocumentExtractionResponse:
    return DocumentExtractionResponse(
        id=value.id,
        source_asset_id=value.source_asset_id,
        source_asset_version_id=value.source_asset_version_id,
        parser_id=value.parser_id,
        parser_version=value.parser_version,
        status=value.status.value,
        extracted_document=value.extracted_document,
        character_count=value.character_count,
        warning_count=value.warning_count,
        truncated=value.truncated,
        created_at=value.created_at,
        schema_version=value.schema_version,
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    "/source-assets/{source_asset_id}/versions/{source_asset_version_id}/extractions",
    response_model=DocumentExtractionMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_extraction(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> DocumentExtractionMutationResponse:
    result: DocumentExtractionResult = service.create(
        context,
        project_id,
        source_asset_id,
        source_asset_version_id,
        idempotency_key=idempotency_key,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    if result.operation.completed_at is None:
        raise RuntimeError("accepted extraction has no completion time")
    return DocumentExtractionMutationResponse(
        extraction=_extraction(result.extraction),
        replayed=result.replayed,
        completed_at=result.operation.completed_at,
        correlation_id=result.operation.correlation_id,
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    "/source-assets/{source_asset_id}/versions/{source_asset_version_id}"
    "/extractions/{extraction_id}",
    response_model=DocumentExtractionResponse,
)
def get_extraction(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    extraction_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> DocumentExtractionResponse:
    return _extraction(
        service.get(context, project_id, source_asset_id, source_asset_version_id, extraction_id)
    )
