from types import TracebackType
from typing import Protocol, Self

from services.api.app.application.repositories import (
    AuditEventRepository,
    BriefIngestionRepository,
    BriefIngestionSourceAssetRepository,
    BriefRepository,
    BriefVersionRepository,
    MembershipRepository,
    OrganizationRepository,
    ProjectRepository,
    RequirementIssueRepository,
    SourceAssetOperationRepository,
    SourceAssetRepository,
    SourceAssetVersionRepository,
    SourceObjectCleanupRequirementRepository,
    SourceObjectRepository,
    SourceObjectUploadRepository,
    WorkspaceRepository,
)


class UnitOfWork(Protocol):
    organizations: OrganizationRepository
    workspaces: WorkspaceRepository
    memberships: MembershipRepository
    projects: ProjectRepository
    briefs: BriefRepository
    brief_ingestions: BriefIngestionRepository
    brief_ingestion_source_assets: BriefIngestionSourceAssetRepository
    brief_versions: BriefVersionRepository
    requirement_issues: RequirementIssueRepository
    source_assets: SourceAssetRepository
    source_asset_versions: SourceAssetVersionRepository
    source_asset_operations: SourceAssetOperationRepository
    source_objects: SourceObjectRepository
    source_object_uploads: SourceObjectUploadRepository
    source_object_cleanup_requirements: SourceObjectCleanupRequirementRepository
    audit_events: AuditEventRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
