from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from services.api.app.application.context import TenantContext
from services.api.app.application.source_asset_services import (
    SourceAssetApplicationService,
    SourceAssetResult,
)
from services.api.app.domain import SourceAsset, SourceAssetVersion
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.ingestion_routes import IdempotencyKey
from services.api.app.presentation.source_asset_schemas import (
    ArchiveSourceAssetRequest,
    CreateSourceAssetRequest,
    CreateSourceAssetVersionRequest,
    SourceAssetDetailResponse,
    SourceAssetListResponse,
    SourceAssetMutationResponse,
    SourceAssetOperationOutcomeResponse,
    SourceAssetResponse,
    SourceAssetVersionListResponse,
    SourceAssetVersionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["source-assets"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> SourceAssetApplicationService:
    return cast(SourceAssetApplicationService, request.app.state.source_asset_application_service)


ServiceDependency = Annotated[SourceAssetApplicationService, Depends(get_service)]


def _asset(asset: SourceAsset) -> SourceAssetResponse:
    return SourceAssetResponse(
        id=asset.id,
        organization_id=asset.organization_id,
        workspace_id=asset.workspace_id,
        project_id=asset.project_id,
        display_name=asset.display_name,
        status=asset.status,
        current_version_id=asset.current_version_id,
        latest_version_number=asset.latest_version_number,
        created_by_actor_subject=asset.created_by_actor_subject,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        version=asset.version,
    )


def _version(version: SourceAssetVersion) -> SourceAssetVersionResponse:
    return SourceAssetVersionResponse(
        id=version.id,
        organization_id=version.organization_id,
        workspace_id=version.workspace_id,
        project_id=version.project_id,
        source_asset_id=version.source_asset_id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        media_type=version.media_type,
        byte_size=version.byte_size,
        checksum_algorithm=version.checksum_algorithm,
        checksum_value=version.checksum_value,
        source_type=version.source_type,
        source_reference=version.source_reference,
        external_record_id=version.external_record_id,
        declared_created_at=version.declared_created_at,
        created_by_actor_subject=version.created_by_actor_subject,
        created_at=version.created_at,
        supersedes_version_id=version.supersedes_version_id,
        metadata_schema_version=version.metadata_schema_version,
    )


def _mutation(result: SourceAssetResult) -> SourceAssetMutationResponse:
    completed_at = result.operation.completed_at
    if completed_at is None:
        raise RuntimeError("accepted source asset operation has no completion time")
    return SourceAssetMutationResponse(
        source_asset=_asset(result.asset),
        current_version=_version(result.version),
        replayed=result.replayed,
        duplicate_content_detected=result.duplicate_count > 0,
        duplicate_count=result.duplicate_count,
        operation=SourceAssetOperationOutcomeResponse(
            operation_id=result.operation.id,
            operation=result.operation.operation,
            submitted_at=result.operation.submitted_at,
            completed_at=completed_at,
            correlation_id=result.operation.correlation_id,
        ),
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets",
    response_model=SourceAssetMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source_asset(
    project_id: UUID,
    payload: CreateSourceAssetRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> SourceAssetMutationResponse:
    result = service.create_asset(
        context,
        project_id,
        idempotency_key=idempotency_key,
        display_name=payload.display_name,
        original_filename=payload.original_filename,
        media_type=payload.media_type.value,
        byte_size=payload.byte_size,
        checksum_algorithm=payload.checksum_algorithm,
        checksum_value=payload.checksum_value,
        source_type=payload.source_type.value,
        source_reference=payload.source_reference,
        external_record_id=payload.external_record_id,
        declared_created_at=payload.declared_created_at,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _mutation(result)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets",
    response_model=SourceAssetListResponse,
)
def list_source_assets(
    project_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> SourceAssetListResponse:
    return SourceAssetListResponse(
        items=[
            _asset(item)
            for item in service.list_assets(context, project_id, limit=limit, offset=offset)
        ],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets/{source_asset_id}",
    response_model=SourceAssetDetailResponse,
)
def get_source_asset(
    project_id: UUID,
    source_asset_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> SourceAssetDetailResponse:
    asset = service.get_asset(context, project_id, source_asset_id)
    version = service.get_version(context, project_id, source_asset_id, asset.current_version_id)
    return SourceAssetDetailResponse(
        source_asset=_asset(asset),
        current_version=_version(version),
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets/{source_asset_id}/versions",
    response_model=SourceAssetMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source_asset_version(
    project_id: UUID,
    source_asset_id: UUID,
    payload: CreateSourceAssetVersionRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
    response: Response,
) -> SourceAssetMutationResponse:
    result = service.create_version(
        context,
        project_id,
        source_asset_id,
        idempotency_key=idempotency_key,
        expected_asset_version=payload.expected_source_asset_version,
        expected_current_version_id=payload.expected_current_version_id,
        source_version_id=payload.source_version_id,
        original_filename=payload.original_filename,
        media_type=payload.media_type.value,
        byte_size=payload.byte_size,
        checksum_algorithm=payload.checksum_algorithm,
        checksum_value=payload.checksum_value,
        source_type=payload.source_type.value,
        source_reference=payload.source_reference,
        external_record_id=payload.external_record_id,
        declared_created_at=payload.declared_created_at,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _mutation(result)


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets/{source_asset_id}/versions",
    response_model=SourceAssetVersionListResponse,
)
def list_source_asset_versions(
    project_id: UUID,
    source_asset_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> SourceAssetVersionListResponse:
    return SourceAssetVersionListResponse(
        items=[
            _version(item) for item in service.list_versions(context, project_id, source_asset_id)
        ]
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets/{source_asset_id}/versions/{source_asset_version_id}",
    response_model=SourceAssetVersionResponse,
)
def get_source_asset_version(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> SourceAssetVersionResponse:
    return _version(
        service.get_version(context, project_id, source_asset_id, source_asset_version_id)
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/source-assets/{source_asset_id}/archive",
    response_model=SourceAssetMutationResponse,
)
def archive_source_asset(
    project_id: UUID,
    source_asset_id: UUID,
    payload: ArchiveSourceAssetRequest,
    context: TenantDependency,
    idempotency_key: IdempotencyKey,
    service: ServiceDependency,
) -> SourceAssetMutationResponse:
    return _mutation(
        service.archive_asset(
            context,
            project_id,
            source_asset_id,
            idempotency_key=idempotency_key,
            expected_asset_version=payload.expected_source_asset_version,
            expected_current_version_id=payload.expected_current_version_id,
        )
    )
