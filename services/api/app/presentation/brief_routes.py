from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from services.api.app.application.brief_services import BriefApplicationService, BriefBundle
from services.api.app.application.context import TenantContext
from services.api.app.domain import RequirementIssueStatus
from services.api.app.presentation.brief_schemas import (
    BriefBundleResponse,
    BriefCreate,
    BriefListResponse,
    BriefResponse,
    BriefTransition,
    BriefVersionCreate,
    BriefVersionListResponse,
    BriefVersionResponse,
    RequirementIssueClose,
    RequirementIssueCreate,
    RequirementIssueListResponse,
    RequirementIssueResponse,
)
from services.api.app.presentation.context import require_tenant_context
from services.api.app.presentation.schemas import AuditEventListResponse, AuditEventResponse

router = APIRouter(prefix="/api/v1", tags=["versioned-brief"])
TenantDependency = Annotated[TenantContext, Depends(require_tenant_context)]


def get_service(request: Request) -> BriefApplicationService:
    return cast(BriefApplicationService, request.app.state.brief_application_service)


ServiceDependency = Annotated[BriefApplicationService, Depends(get_service)]


def _bundle(bundle: BriefBundle) -> BriefBundleResponse:
    return BriefBundleResponse(
        brief=BriefResponse.model_validate(bundle.brief),
        current_version=BriefVersionResponse.model_validate(bundle.current_version),
        issues=[RequirementIssueResponse.model_validate(issue) for issue in bundle.issues],
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs",
    response_model=BriefBundleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_brief(
    project_id: UUID,
    payload: BriefCreate,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefBundleResponse:
    return _bundle(
        service.create_brief(
            context,
            project_id,
            title=payload.title,
            structured_content=payload.structured_content,
            source_type=payload.source_type,
            source_reference=payload.source_reference,
            change_summary=payload.change_summary,
        )
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs",
    response_model=BriefListResponse,
)
def list_briefs(
    project_id: UUID, context: TenantDependency, service: ServiceDependency
) -> BriefListResponse:
    return BriefListResponse(
        items=[
            BriefResponse.model_validate(item) for item in service.list_briefs(context, project_id)
        ]
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}",
    response_model=BriefBundleResponse,
)
def get_brief(
    project_id: UUID,
    brief_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefBundleResponse:
    return _bundle(service.get_brief(context, project_id, brief_id))


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions",
    response_model=BriefVersionListResponse,
)
def list_versions(
    project_id: UUID,
    brief_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefVersionListResponse:
    return BriefVersionListResponse(
        items=[
            BriefVersionResponse.model_validate(item)
            for item in service.list_versions(context, project_id, brief_id)
        ]
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{version_id}",
    response_model=BriefVersionResponse,
)
def get_version(
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefVersionResponse:
    return BriefVersionResponse.model_validate(
        service.get_version(context, project_id, brief_id, version_id)
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions",
    response_model=BriefBundleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    project_id: UUID,
    brief_id: UUID,
    payload: BriefVersionCreate,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefBundleResponse:
    return _bundle(
        service.create_version(
            context,
            project_id,
            brief_id,
            expected_brief_version=payload.expected_brief_version,
            expected_current_version_id=payload.expected_current_version_id,
            source_version_id=payload.source_version_id,
            structured_content=payload.structured_content,
            source_type=payload.source_type,
            source_reference=payload.source_reference,
            change_summary=payload.change_summary,
        )
    )


def _transition(
    action: str,
    service: BriefApplicationService,
    context: TenantContext,
    project_id: UUID,
    brief_id: UUID,
    payload: BriefTransition,
) -> BriefBundleResponse:
    method = {"submit": service.submit, "approve": service.approve, "archive": service.archive}[
        action
    ]
    return _bundle(
        method(
            context,
            project_id,
            brief_id,
            expected_brief_version=payload.expected_brief_version,
            expected_current_version_id=payload.expected_current_version_id,
        )
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/submit",
    response_model=BriefBundleResponse,
)
def submit_brief(
    project_id: UUID,
    brief_id: UUID,
    payload: BriefTransition,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefBundleResponse:
    return _transition("submit", service, context, project_id, brief_id, payload)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/approve",
    response_model=BriefBundleResponse,
)
def approve_brief(
    project_id: UUID,
    brief_id: UUID,
    payload: BriefTransition,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefBundleResponse:
    return _transition("approve", service, context, project_id, brief_id, payload)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/archive",
    response_model=BriefBundleResponse,
)
def archive_brief(
    project_id: UUID,
    brief_id: UUID,
    payload: BriefTransition,
    context: TenantDependency,
    service: ServiceDependency,
) -> BriefBundleResponse:
    return _transition("archive", service, context, project_id, brief_id, payload)


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{version_id}/issues",
    response_model=RequirementIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_issue(
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    payload: RequirementIssueCreate,
    context: TenantDependency,
    service: ServiceDependency,
) -> RequirementIssueResponse:
    return RequirementIssueResponse.model_validate(
        service.create_issue(
            context,
            project_id,
            brief_id,
            version_id,
            expected_brief_version=payload.expected_brief_version,
            expected_current_version_id=payload.expected_current_version_id,
            issue_type=payload.issue_type,
            field_path=payload.field_path,
            severity=payload.severity,
            message=payload.message,
        )
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{version_id}/issues",
    response_model=RequirementIssueListResponse,
)
def list_issues(
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> RequirementIssueListResponse:
    return RequirementIssueListResponse(
        items=[
            RequirementIssueResponse.model_validate(item)
            for item in service.list_issues(context, project_id, brief_id, version_id)
        ]
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{version_id}/issues/{issue_id}",
    response_model=RequirementIssueResponse,
)
def get_issue(
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    issue_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> RequirementIssueResponse:
    return RequirementIssueResponse.model_validate(
        service.get_issue(context, project_id, brief_id, version_id, issue_id)
    )


def _close_issue(
    target_status: RequirementIssueStatus,
    service: BriefApplicationService,
    context: TenantContext,
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    issue_id: UUID,
    payload: RequirementIssueClose,
) -> RequirementIssueResponse:
    return RequirementIssueResponse.model_validate(
        service.close_issue(
            context,
            project_id,
            brief_id,
            version_id,
            issue_id,
            expected_brief_version=payload.expected_brief_version,
            expected_current_version_id=payload.expected_current_version_id,
            expected_issue_version=payload.expected_issue_version,
            resolution_note=payload.resolution_note,
            target_status=target_status,
        )
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{version_id}/issues/{issue_id}/resolve",
    response_model=RequirementIssueResponse,
)
def resolve_issue(
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    issue_id: UUID,
    payload: RequirementIssueClose,
    context: TenantDependency,
    service: ServiceDependency,
) -> RequirementIssueResponse:
    return _close_issue(
        RequirementIssueStatus.RESOLVED,
        service,
        context,
        project_id,
        brief_id,
        version_id,
        issue_id,
        payload,
    )


@router.post(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/versions/{version_id}/issues/{issue_id}/dismiss",
    response_model=RequirementIssueResponse,
)
def dismiss_issue(
    project_id: UUID,
    brief_id: UUID,
    version_id: UUID,
    issue_id: UUID,
    payload: RequirementIssueClose,
    context: TenantDependency,
    service: ServiceDependency,
) -> RequirementIssueResponse:
    return _close_issue(
        RequirementIssueStatus.DISMISSED,
        service,
        context,
        project_id,
        brief_id,
        version_id,
        issue_id,
        payload,
    )


@router.get(
    "/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/briefs/{brief_id}/audit-events",
    response_model=AuditEventListResponse,
)
def list_brief_audit_events(
    project_id: UUID,
    brief_id: UUID,
    context: TenantDependency,
    service: ServiceDependency,
) -> AuditEventListResponse:
    return AuditEventListResponse(
        items=[
            AuditEventResponse.model_validate(item)
            for item in service.list_audit_events(context, project_id, brief_id)
        ]
    )
