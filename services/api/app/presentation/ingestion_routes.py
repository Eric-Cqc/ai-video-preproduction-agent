import re
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status

from services.api.app.application.context import TenantContext
from services.api.app.application.errors import InvalidRequest
from services.api.app.application.ingestion_services import (
    BriefIngestionApplicationService,
    BriefSourceAttachmentInput,
    IngestionResult,
)
from services.api.app.presentation.brief_routes import _bundle
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_schemas import (
    BriefIngestionCreate,
    BriefIngestionResponse,
    BriefIngestionSourceAttachmentResponse,
    BriefVersionIngestionCreate,
)

router = APIRouter(prefix="/api/v1", tags=["structured-brief-ingestion"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[!-~]{8,128}$")


def require_idempotency_key(
    value: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if value is None or not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise InvalidRequest("Idempotency-Key is required and invalid")
    return value


IdempotencyKey = Annotated[str, Depends(require_idempotency_key)]


def get_service(request: Request) -> BriefIngestionApplicationService:
    return cast(BriefIngestionApplicationService, request.app.state.ingestion_application_service)


ServiceDependency = Annotated[BriefIngestionApplicationService, Depends(get_service)]


def _response(result: IngestionResult) -> BriefIngestionResponse:
    completed_at = result.ingestion.completed_at
    if completed_at is None:
        raise RuntimeError("accepted ingestion has no completion time")
    return BriefIngestionResponse(
        ingestion_id=result.ingestion.id,
        operation=result.ingestion.operation,
        source_type=result.ingestion.source_type,
        schema_version=result.ingestion.schema_version,
        submitted_at=result.ingestion.submitted_at,
        completed_at=completed_at,
        correlation_id=result.ingestion.correlation_id,
        replayed=result.replayed,
        result=_bundle(result.bundle),
        source_attachments=[
            BriefIngestionSourceAttachmentResponse(
                source_asset_id=item.source_asset_id,
                source_asset_version_id=item.source_asset_version_id,
                relation_type=item.relation_type,
                position=item.position,
            )
            for item in result.source_attachments
        ],
    )


def _attachments(
    payload: BriefIngestionCreate | BriefVersionIngestionCreate,
) -> list[BriefSourceAttachmentInput]:
    return [
        BriefSourceAttachmentInput(
            source_asset_id=item.source_asset_id,
            source_asset_version_id=item.source_asset_version_id,
            relation_type=item.relation_type,
        )
        for item in payload.source_attachments
    ]


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/brief-ingestions",
    response_model=BriefIngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_brief_ingestion(
    project_id: UUID,
    payload: BriefIngestionCreate,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> BriefIngestionResponse:
    result = service.create_brief(
        context,
        project_id,
        idempotency_key=idempotency_key,
        title=payload.title,
        structured_content=payload.structured_content,
        source_type=payload.source_type,
        source_reference=payload.source_reference,
        change_summary=payload.change_summary,
        source_attachments=_attachments(payload),
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _response(result)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/ingestions",
    response_model=BriefIngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version_ingestion(
    project_id: UUID,
    brief_id: UUID,
    payload: BriefVersionIngestionCreate,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> BriefIngestionResponse:
    result = service.create_version(
        context,
        project_id,
        brief_id,
        idempotency_key=idempotency_key,
        expected_brief_version=payload.expected_brief_version,
        expected_current_version_id=payload.expected_current_version_id,
        source_version_id=payload.source_version_id,
        structured_content=payload.structured_content,
        source_type=payload.source_type,
        source_reference=payload.source_reference,
        change_summary=payload.change_summary,
        source_attachments=_attachments(payload),
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _response(result)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/brief-ingestions/{ingestion_id}",
    response_model=BriefIngestionResponse,
)
def get_ingestion(
    project_id: UUID,
    ingestion_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefIngestionResponse:
    return _response(service.get(context, project_id, ingestion_id))
