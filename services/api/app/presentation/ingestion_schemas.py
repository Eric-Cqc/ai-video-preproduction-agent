from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.domain import (
    BriefIngestionOperation,
    BriefIngestionSourceAssetRelationType,
    BriefIngestionSourceType,
)
from services.api.app.presentation.brief_schemas import BriefBundleResponse

SOURCE_REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"
MAX_SOURCE_ATTACHMENTS = 10


class BriefIngestionSourceAttachmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_asset_id: UUID
    source_asset_version_id: UUID
    relation_type: BriefIngestionSourceAssetRelationType


class BriefIngestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal[BriefIngestionOperation.CREATE_BRIEF]
    title: str = Field(min_length=1, max_length=200)
    structured_content: dict[str, object]
    source_type: BriefIngestionSourceType
    source_reference: str | None = Field(default=None, pattern=SOURCE_REFERENCE_PATTERN)
    change_summary: str = Field(min_length=1, max_length=500)
    source_attachments: list[BriefIngestionSourceAttachmentCreate] = Field(
        default_factory=list, max_length=MAX_SOURCE_ATTACHMENTS
    )


class BriefVersionIngestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal[BriefIngestionOperation.CREATE_VERSION]
    expected_brief_version: int = Field(ge=1)
    expected_current_version_id: UUID
    source_version_id: UUID
    structured_content: dict[str, object]
    source_type: BriefIngestionSourceType
    source_reference: str | None = Field(default=None, pattern=SOURCE_REFERENCE_PATTERN)
    change_summary: str = Field(min_length=1, max_length=500)
    source_attachments: list[BriefIngestionSourceAttachmentCreate] = Field(
        default_factory=list, max_length=MAX_SOURCE_ATTACHMENTS
    )


class BriefIngestionSourceAttachmentResponse(BaseModel):
    source_asset_id: UUID
    source_asset_version_id: UUID
    relation_type: BriefIngestionSourceAssetRelationType
    position: int


class BriefIngestionResponse(BaseModel):
    ingestion_id: UUID
    operation: BriefIngestionOperation
    source_type: BriefIngestionSourceType
    schema_version: str
    submitted_at: datetime
    completed_at: datetime
    correlation_id: str
    replayed: bool
    result: BriefBundleResponse
    source_attachments: list[BriefIngestionSourceAttachmentResponse]
