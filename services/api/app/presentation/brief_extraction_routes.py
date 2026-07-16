from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from services.api.app.application.brief_extraction_services import StructuredBriefExtractionService
from services.api.app.application.context import TenantContext
from services.api.app.presentation.context import require_tenant_context

router = APIRouter(prefix="/api/v1", tags=["brief-extraction"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> StructuredBriefExtractionService:
    return cast(StructuredBriefExtractionService, request.app.state.brief_extraction_service)


ServiceDependency = Annotated[StructuredBriefExtractionService, Depends(get_service)]


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    "/source-assets/{source_asset_id}/versions/{source_asset_version_id}"
    "/extractions/{document_extraction_id}/brief-extraction-runs",
    status_code=status.HTTP_201_CREATED,
)
def extract_brief(
    project_id: UUID,
    source_asset_id: UUID,
    source_asset_version_id: UUID,
    document_extraction_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> dict[str, object]:
    result = service.extract(
        context,
        project_id,
        source_asset_id,
        source_asset_version_id,
        document_extraction_id,
    )
    return {
        "run_id": result.run.id,
        "status": result.run.status,
        "candidate_available": result.run.candidate_structured_brief is not None,
    }
