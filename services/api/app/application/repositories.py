from datetime import datetime
from typing import Protocol
from uuid import UUID

from services.api.app.domain import (
    AuditEvent,
    Brief,
    BriefIngestion,
    BriefIngestionOperation,
    BriefIngestionSourceAsset,
    BriefVersion,
    Membership,
    Organization,
    Project,
    RequirementIssue,
    RequirementIssueStatus,
    SourceAsset,
    SourceAssetOperation,
    SourceAssetOperationType,
    SourceAssetVersion,
    SourceObject,
    SourceObjectCleanupRequirement,
    SourceObjectUpload,
    Workspace,
)


class OrganizationRepository(Protocol):
    def add(self, organization: Organization) -> Organization: ...

    def get(self, organization_id: UUID) -> Organization | None: ...


class WorkspaceRepository(Protocol):
    def add(self, workspace: Workspace) -> Workspace: ...

    def get(self, organization_id: UUID, workspace_id: UUID) -> Workspace | None: ...


class MembershipRepository(Protocol):
    def add(self, membership: Membership) -> Membership: ...

    def find_any_for_organization(
        self, organization_id: UUID, actor_subject: str
    ) -> Membership | None: ...

    def find_effective(
        self, organization_id: UUID, workspace_id: UUID, actor_subject: str
    ) -> Membership | None: ...

    def find_organization_wide(
        self, organization_id: UUID, actor_subject: str
    ) -> Membership | None: ...


class ProjectRepository(Protocol):
    def add(self, project: Project) -> Project: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> Project | None: ...

    def list(self, organization_id: UUID, workspace_id: UUID) -> list[Project]: ...

    def update(self, project: Project, *, expected_version: int) -> Project: ...


class BriefRepository(Protocol):
    def add(self, brief: Brief) -> Brief: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> Brief | None: ...

    def list(self, organization_id: UUID, workspace_id: UUID, project_id: UUID) -> list[Brief]: ...

    def update(
        self,
        brief: Brief,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> Brief: ...


class BriefIngestionRepository(Protocol):
    def reserve(self, ingestion: BriefIngestion) -> BriefIngestion | None: ...

    def finalize_accepted(
        self,
        ingestion: BriefIngestion,
        *,
        brief_id: UUID,
        brief_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> BriefIngestion: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, ingestion_id: UUID
    ) -> BriefIngestion | None: ...

    def get_by_idempotency_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: BriefIngestionOperation,
        idempotency_key: str,
    ) -> BriefIngestion | None: ...


class BriefIngestionSourceAssetRepository(Protocol):
    def add_for_accepted_ingestion(
        self, attachment: BriefIngestionSourceAsset
    ) -> BriefIngestionSourceAsset: ...

    def list_for_ingestion(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_ingestion_id: UUID
    ) -> list[BriefIngestionSourceAsset]: ...


class BriefVersionRepository(Protocol):
    def add(self, version: BriefVersion) -> BriefVersion: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> BriefVersion | None: ...

    def list(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, brief_id: UUID
    ) -> list[BriefVersion]: ...

    def submit_for_review(self, version: BriefVersion) -> BriefVersion: ...

    def approve(self, version: BriefVersion) -> BriefVersion: ...

    def supersede(self, version: BriefVersion) -> BriefVersion: ...


class SourceAssetRepository(Protocol):
    def add(self, asset: SourceAsset) -> SourceAsset: ...

    def get(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> SourceAsset | None: ...

    def list(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[SourceAsset]: ...

    def compare_and_move_pointer(
        self,
        asset: SourceAsset,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAsset: ...

    def compare_and_archive(
        self,
        asset: SourceAsset,
        *,
        expected_version: int,
        expected_current_version_id: UUID,
    ) -> SourceAsset: ...


class SourceAssetVersionRepository(Protocol):
    def add(self, version: SourceAssetVersion) -> SourceAssetVersion: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        version_id: UUID,
    ) -> SourceAssetVersion | None: ...

    def list_for_asset(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID, source_asset_id: UUID
    ) -> list[SourceAssetVersion]: ...

    def find_declared_duplicate_within_project(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        *,
        checksum_algorithm: str,
        checksum_value: str,
        byte_size: int,
        media_type: str,
        exclude_source_asset_id: UUID | None = None,
    ) -> int: ...


class SourceAssetOperationRepository(Protocol):
    def reserve(self, operation: SourceAssetOperation) -> SourceAssetOperation | None: ...

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: SourceAssetOperationType,
        idempotency_key: str,
    ) -> SourceAssetOperation | None: ...

    def finalize_accepted(
        self,
        operation: SourceAssetOperation,
        *,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> SourceAssetOperation: ...


class SourceObjectRepository(Protocol):
    def add(self, source_object: SourceObject) -> SourceObject: ...

    def get_for_version(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        source_asset_version_id: UUID,
    ) -> SourceObject | None: ...


class SourceObjectUploadRepository(Protocol):
    def reserve(self, upload: SourceObjectUpload) -> SourceObjectUpload | None: ...

    def get_scoped_by_key(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> SourceObjectUpload | None: ...

    def finalize_accepted(
        self,
        upload: SourceObjectUpload,
        *,
        source_object_id: UUID,
        completed_at: datetime,
        expected_version: int,
    ) -> SourceObjectUpload: ...


class SourceObjectCleanupRequirementRepository(Protocol):
    def add(
        self, requirement: SourceObjectCleanupRequirement
    ) -> SourceObjectCleanupRequirement: ...


class RequirementIssueRepository(Protocol):
    def add(self, issue: RequirementIssue) -> RequirementIssue: ...

    def get(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
        issue_id: UUID,
    ) -> RequirementIssue | None: ...

    def list(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> list[RequirementIssue]: ...

    def count_open_blocking(
        self,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        brief_id: UUID,
        version_id: UUID,
    ) -> int: ...

    def update(
        self,
        issue: RequirementIssue,
        *,
        expected_version: int,
        expected_status: RequirementIssueStatus,
    ) -> RequirementIssue: ...


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...

    def list_for_project(
        self, organization_id: UUID, workspace_id: UUID, project_id: UUID
    ) -> list[AuditEvent]: ...

    def list_for_brief(
        self, organization_id: UUID, workspace_id: UUID, brief_id: UUID
    ) -> list[AuditEvent]: ...
