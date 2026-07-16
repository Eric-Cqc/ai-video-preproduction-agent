from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.domain import (
    SourceAssetMediaType,
    SourceAssetOperationType,
    SourceAssetSourceType,
    SourceAssetStatus,
)
from services.api.app.domain.source_asset import MAX_DECLARED_BYTE_SIZE


class SourceAssetMetadataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_filename: str = Field(min_length=1, max_length=255)
    media_type: SourceAssetMediaType
    byte_size: int = Field(gt=0, le=MAX_DECLARED_BYTE_SIZE)
    checksum_algorithm: str = Field(pattern=r"^sha256$")
    checksum_value: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: SourceAssetSourceType
    source_reference: str | None = Field(default=None, max_length=500)
    external_record_id: str | None = Field(default=None, max_length=200)
    declared_created_at: datetime | None = None


class CreateSourceAssetRequest(SourceAssetMetadataRequest):
    display_name: str = Field(min_length=1, max_length=200)


class CreateSourceAssetVersionRequest(SourceAssetMetadataRequest):
    expected_source_asset_version: int = Field(ge=1)
    expected_current_version_id: UUID
    source_version_id: UUID


class ArchiveSourceAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_source_asset_version: int = Field(ge=1)
    expected_current_version_id: UUID


class SourceAssetResponse(BaseModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    display_name: str
    status: SourceAssetStatus
    current_version_id: UUID
    latest_version_number: int
    created_by_actor_subject: str
    created_at: datetime
    updated_at: datetime
    version: int


class SourceAssetVersionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    source_asset_id: UUID
    version_number: int
    original_filename: str
    media_type: SourceAssetMediaType
    byte_size: int
    checksum_algorithm: str
    checksum_value: str
    source_type: SourceAssetSourceType
    source_reference: str | None
    external_record_id: str | None
    declared_created_at: datetime | None
    created_by_actor_subject: str
    created_at: datetime
    supersedes_version_id: UUID | None
    metadata_schema_version: str


class SourceAssetOperationOutcomeResponse(BaseModel):
    operation_id: UUID
    operation: SourceAssetOperationType
    submitted_at: datetime
    completed_at: datetime
    correlation_id: str


class SourceAssetMutationResponse(BaseModel):
    source_asset: SourceAssetResponse
    current_version: SourceAssetVersionResponse
    replayed: bool
    duplicate_content_detected: bool
    duplicate_count: int
    operation: SourceAssetOperationOutcomeResponse


class SourceAssetDetailResponse(BaseModel):
    source_asset: SourceAssetResponse
    current_version: SourceAssetVersionResponse


class SourceAssetListResponse(BaseModel):
    items: list[SourceAssetResponse]
    limit: int
    offset: int


class SourceAssetVersionListResponse(BaseModel):
    items: list[SourceAssetVersionResponse]


class SourceObjectResponse(BaseModel):
    id: UUID
    source_asset_id: UUID
    source_asset_version_id: UUID
    state: str
    observed_byte_size: int
    created_at: datetime


class SourceObjectUploadResponse(BaseModel):
    source_object: SourceObjectResponse
    replayed: bool
    completed_at: datetime
    correlation_id: str
