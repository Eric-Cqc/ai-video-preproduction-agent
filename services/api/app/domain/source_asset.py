import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from services.api.app.domain.errors import InvalidSourceAssetMutation, VersionConflict

MAX_DECLARED_BYTE_SIZE = 100 * 1024 * 1024
SOURCE_ASSET_METADATA_SCHEMA_VERSION = "1.0.0"
MAX_DISPLAY_NAME_LENGTH = 200
MAX_FILENAME_LENGTH = 255
MAX_SOURCE_REFERENCE_LENGTH = 500
MAX_EXTERNAL_RECORD_ID_LENGTH = 200

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNIX_ABSOLUTE_RE = re.compile(r"^/")
_HOME_RE = re.compile(r"^~[\\/]")
_UNC_RE = re.compile(r"^\\\\")
_DATABASE_URL_RE = re.compile(r"^(postgresql?|mysql|mongodb(?:\+srv)?|redis)://", re.IGNORECASE)
_AUTHORITY_WITH_CREDENTIALS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://[^/\s]*@", re.IGNORECASE)
_SECRET_LIKE_RE = re.compile(
    r"(authorization|bearer|token|access[_-]?token|refresh[_-]?token|api[_-]?key|"
    r"secret|password)",
    re.IGNORECASE,
)
_SIGNED_QUERY_RE = re.compile(
    r"(\?|&)(x-amz-signature|x-goog-signature|signature|sig|token|access_token)=",
    re.IGNORECASE,
)


class SourceAssetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class SourceAssetMediaType(StrEnum):
    PDF = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    TEXT = "text/plain"
    CSV = "text/csv"
    JSON = "application/json"


class SourceAssetSourceType(StrEnum):
    MANUAL_METADATA = "manual_metadata"
    EXTERNAL_SYSTEM = "external_system"
    API_DECLARED = "api_declared"


class SourceAssetOperationType(StrEnum):
    CREATE_SOURCE_ASSET = "create_source_asset"
    CREATE_SOURCE_ASSET_VERSION = "create_source_asset_version"
    ARCHIVE_SOURCE_ASSET = "archive_source_asset"


class SourceAssetOperationStatus(StrEnum):
    RESERVED = "reserved"
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class SourceAsset:
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

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        display_name: str,
        initial_version_id: UUID,
        created_by_actor_subject: str,
        now: datetime,
    ) -> "SourceAsset":
        return cls(
            id=id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            project_id=project_id,
            display_name=validate_display_name(display_name),
            status=SourceAssetStatus.ACTIVE,
            current_version_id=initial_version_id,
            latest_version_number=1,
            created_by_actor_subject=created_by_actor_subject,
            created_at=now,
            updated_at=now,
            version=1,
        )

    def new_version(
        self, *, expected_version: int, new_version_id: UUID, now: datetime
    ) -> "SourceAsset":
        self._require_version(expected_version)
        if self.status is SourceAssetStatus.ARCHIVED:
            raise InvalidSourceAssetMutation("archived source assets cannot receive new versions")
        return replace(
            self,
            current_version_id=new_version_id,
            latest_version_number=self.latest_version_number + 1,
            updated_at=now,
            version=self.version + 1,
        )

    def archive(self, *, expected_version: int, now: datetime) -> "SourceAsset":
        self._require_version(expected_version)
        if self.status is SourceAssetStatus.ARCHIVED:
            raise InvalidSourceAssetMutation("source asset is already archived")
        return replace(
            self,
            status=SourceAssetStatus.ARCHIVED,
            updated_at=now,
            version=self.version + 1,
        )

    def _require_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise VersionConflict(
                "expected source asset version "
                f"{expected_version}, current version is {self.version}"
            )


@dataclass(frozen=True, slots=True)
class SourceAssetVersion:
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

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        organization_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        source_asset_id: UUID,
        version_number: int,
        original_filename: str,
        media_type: str,
        byte_size: int,
        checksum_algorithm: str,
        checksum_value: str,
        source_type: str,
        source_reference: str | None,
        external_record_id: str | None,
        declared_created_at: datetime | None,
        created_by_actor_subject: str,
        created_at: datetime,
        supersedes_version_id: UUID | None,
        metadata_schema_version: str = SOURCE_ASSET_METADATA_SCHEMA_VERSION,
    ) -> "SourceAssetVersion":
        if version_number < 1:
            raise InvalidSourceAssetMutation("source asset version number must be >= 1")
        if metadata_schema_version != SOURCE_ASSET_METADATA_SCHEMA_VERSION:
            raise InvalidSourceAssetMutation("unsupported source asset metadata schema version")
        return cls(
            id=id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            project_id=project_id,
            source_asset_id=source_asset_id,
            version_number=version_number,
            original_filename=validate_original_filename(original_filename),
            media_type=validate_media_type(media_type),
            byte_size=validate_byte_size(byte_size),
            checksum_algorithm=validate_checksum_algorithm(checksum_algorithm),
            checksum_value=validate_checksum_value(checksum_value),
            source_type=validate_source_type(source_type),
            source_reference=validate_source_reference(source_reference),
            external_record_id=validate_external_record_id(external_record_id),
            declared_created_at=declared_created_at,
            created_by_actor_subject=created_by_actor_subject,
            created_at=created_at,
            supersedes_version_id=supersedes_version_id,
            metadata_schema_version=metadata_schema_version,
        )


@dataclass(frozen=True, slots=True)
class SourceAssetOperation:
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    project_id: UUID
    source_asset_id: UUID | None
    source_asset_version_id: UUID | None
    operation: SourceAssetOperationType
    idempotency_key: str
    request_digest: str
    status: SourceAssetOperationStatus
    submitted_by_actor_subject: str
    submitted_at: datetime
    completed_at: datetime | None
    correlation_id: str
    version: int


def validate_display_name(value: str) -> str:
    return _validate_bounded_single_line(value, "display_name", MAX_DISPLAY_NAME_LENGTH)


def validate_original_filename(value: str) -> str:
    validated = _validate_bounded_single_line(value, "original_filename", MAX_FILENAME_LENGTH)
    if "/" in validated or "\\" in validated or ".." in validated:
        raise InvalidSourceAssetMutation("original_filename must not be a path")
    return validated


def validate_checksum_algorithm(value: str) -> str:
    if value != "sha256":
        raise InvalidSourceAssetMutation("checksum_algorithm must be sha256")
    return value


def validate_checksum_value(value: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise InvalidSourceAssetMutation("checksum_value must be a lowercase SHA-256 hex digest")
    return value


def validate_media_type(value: str) -> SourceAssetMediaType:
    try:
        return SourceAssetMediaType(value)
    except ValueError as error:
        raise InvalidSourceAssetMutation("unsupported source asset media_type") from error


def validate_source_type(value: str) -> SourceAssetSourceType:
    try:
        return SourceAssetSourceType(value)
    except ValueError as error:
        raise InvalidSourceAssetMutation("unsupported source asset source_type") from error


def validate_byte_size(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidSourceAssetMutation("byte_size must be an integer")
    if value <= 0 or value > MAX_DECLARED_BYTE_SIZE:
        raise InvalidSourceAssetMutation("byte_size must be between 1 byte and 100 MiB")
    return value


def validate_source_reference(value: str | None) -> str | None:
    return _validate_optional_reference(value, "source_reference", MAX_SOURCE_REFERENCE_LENGTH)


def validate_external_record_id(value: str | None) -> str | None:
    return _validate_optional_reference(value, "external_record_id", MAX_EXTERNAL_RECORD_ID_LENGTH)


def _validate_optional_reference(value: str | None, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    validated = _validate_bounded_single_line(value, field, max_length)
    if _UNIX_ABSOLUTE_RE.match(validated) or _HOME_RE.match(validated):
        raise InvalidSourceAssetMutation(f"{field} must not be a local path")
    if _WINDOWS_DRIVE_RE.match(validated) or _UNC_RE.match(validated):
        raise InvalidSourceAssetMutation(f"{field} must not be a local path")
    lowered = validated.lower()
    if lowered.startswith("file://") or _DATABASE_URL_RE.match(validated):
        raise InvalidSourceAssetMutation(f"{field} must not contain local or database URLs")
    if _AUTHORITY_WITH_CREDENTIALS_RE.match(validated):
        raise InvalidSourceAssetMutation(f"{field} must not contain credentials")
    if _SECRET_LIKE_RE.search(validated) or _SIGNED_QUERY_RE.search(validated):
        raise InvalidSourceAssetMutation(f"{field} must not contain credential-like values")
    return validated


def _validate_bounded_single_line(value: str, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise InvalidSourceAssetMutation(f"{field} must be a string")
    if not value.strip():
        raise InvalidSourceAssetMutation(f"{field} must not be blank")
    if len(value) > max_length:
        raise InvalidSourceAssetMutation(f"{field} is too long")
    if _CONTROL_RE.search(value):
        raise InvalidSourceAssetMutation(f"{field} must not contain control characters")
    return value.strip()
