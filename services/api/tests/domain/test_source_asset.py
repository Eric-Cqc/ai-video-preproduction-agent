from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from services.api.app.domain import (
    InvalidSourceAssetMutation,
    SourceAsset,
    SourceAssetMediaType,
    SourceAssetSourceType,
    SourceAssetStatus,
    SourceAssetVersion,
    VersionConflict,
)
from services.api.app.domain.source_asset import MAX_DECLARED_BYTE_SIZE


def _asset(*, current_version_id: UUID | None = None) -> SourceAsset:
    now = datetime.now(UTC)
    return SourceAsset.create(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        display_name=" Strategy Brief.pdf ",
        initial_version_id=current_version_id or uuid4(),
        created_by_actor_subject="actor:owner",
        now=now,
    )


def _version(
    *,
    source_asset_id: UUID | None = None,
    version_number: int = 1,
    supersedes_version_id: UUID | None = None,
    original_filename: str = "Strategy Brief.pdf",
    media_type: str = SourceAssetMediaType.PDF.value,
    byte_size: int = 1024,
    checksum_algorithm: str = "sha256",
    checksum_value: str = "a" * 64,
    source_type: str = SourceAssetSourceType.API_DECLARED.value,
    source_reference: str | None = "https://example.invalid/reference/asset",
    external_record_id: str | None = "external-123",
) -> SourceAssetVersion:
    now = datetime.now(UTC)
    return SourceAssetVersion.create(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        source_asset_id=source_asset_id or uuid4(),
        version_number=version_number,
        original_filename=original_filename,
        media_type=media_type,
        byte_size=byte_size,
        checksum_algorithm=checksum_algorithm,
        checksum_value=checksum_value,
        source_type=source_type,
        source_reference=source_reference,
        external_record_id=external_record_id,
        declared_created_at=None,
        created_by_actor_subject="actor:owner",
        created_at=now,
        supersedes_version_id=supersedes_version_id,
    )


def test_source_asset_creation_successor_and_archive() -> None:
    asset = _asset()
    predecessor = _version(source_asset_id=asset.id)
    before = asdict(predecessor)
    new_version_id = uuid4()

    successor_asset = asset.new_version(
        expected_version=1, new_version_id=new_version_id, now=datetime.now(UTC)
    )
    successor_version = _version(
        source_asset_id=asset.id,
        version_number=2,
        supersedes_version_id=predecessor.id,
        original_filename="Strategy Brief v2.pdf",
    )
    archived = successor_asset.archive(expected_version=2, now=datetime.now(UTC))

    assert asset.status is SourceAssetStatus.ACTIVE
    assert asset.version == 1
    assert asset.latest_version_number == 1
    assert successor_asset.current_version_id == new_version_id
    assert successor_asset.latest_version_number == 2
    assert successor_asset.version == 2
    assert successor_version.supersedes_version_id == predecessor.id
    assert successor_version.version_number == 2
    assert asdict(predecessor) == before
    assert archived.status is SourceAssetStatus.ARCHIVED
    assert archived.version == 3


def test_source_asset_rejects_stale_or_archived_mutations() -> None:
    asset = _asset()
    archived = asset.archive(expected_version=1, now=datetime.now(UTC))

    with pytest.raises(VersionConflict):
        asset.new_version(expected_version=2, new_version_id=uuid4(), now=datetime.now(UTC))
    with pytest.raises(InvalidSourceAssetMutation):
        archived.new_version(expected_version=2, new_version_id=uuid4(), now=datetime.now(UTC))
    with pytest.raises(InvalidSourceAssetMutation):
        archived.archive(expected_version=2, now=datetime.now(UTC))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"original_filename": ""},
        {"original_filename": "   "},
        {"original_filename": "../brief.pdf"},
        {"original_filename": "folder/brief.pdf"},
        {"original_filename": "folder\\brief.pdf"},
        {"original_filename": "brief\n.pdf"},
        {"checksum_algorithm": "md5"},
        {"checksum_algorithm": "sha1"},
        {"checksum_value": "A" * 64},
        {"checksum_value": "g" * 64},
        {"checksum_value": "a" * 63},
        {"media_type": "image/png"},
        {"media_type": "application/octet-stream"},
        {"byte_size": 0},
        {"byte_size": -1},
        {"byte_size": MAX_DECLARED_BYTE_SIZE + 1},
        {"byte_size": 1.5},
        {"source_type": "uploaded_bytes"},
        {"source_reference": "/tmp/brief.pdf"},
        {"source_reference": "~/brief.pdf"},
        {"source_reference": "C:\\Users\\brief.pdf"},
        {"source_reference": "\\\\server\\share\\brief.pdf"},
        {"source_reference": "file:///tmp/brief.pdf"},
        {"source_reference": "postgresql://user:pass@db/app"},
        {"source_reference": "https://user:pass@example.invalid/file"},
        {"source_reference": "https://example.invalid/file?X-Amz-Signature=abc"},
        {"source_reference": "Bearer abc"},
        {"external_record_id": "/tmp/brief.pdf"},
        {"external_record_id": "token=abc"},
    ],
)
def test_source_asset_version_validation_rejects_invalid_metadata(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(InvalidSourceAssetMutation):
        _version(**kwargs)
