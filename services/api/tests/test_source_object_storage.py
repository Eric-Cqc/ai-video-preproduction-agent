import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from services.api.app.application.storage import (
    LocalFilesystemStorageAdapter,
    StorageError,
    StorageValidationError,
)


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


def test_local_storage_streams_finalizes_and_survives_restart(tmp_path: Path) -> None:
    adapter = LocalFilesystemStorageAdapter(tmp_path)
    staged = asyncio.run(adapter.stage(_chunks(b"alpha", b"-beta"), max_bytes=64))
    final_key = adapter.new_final_key()
    adapter.finalize(staged.storage_key, final_key)

    restarted = LocalFilesystemStorageAdapter(tmp_path)
    assert b"".join(restarted.read(final_key, chunk_size=3)) == b"alpha-beta"
    assert not any(restarted.staging_root.iterdir())
    assert final_key.startswith("object-")

    with pytest.raises(StorageError):
        adapter.finalize(final_key, final_key)


@pytest.mark.parametrize("values,max_bytes", [((b"",), 10), ((b"123", b"456"), 5)])
def test_local_storage_rejects_empty_and_oversized_streams(
    tmp_path: Path, values: tuple[bytes, ...], max_bytes: int
) -> None:
    adapter = LocalFilesystemStorageAdapter(tmp_path)
    with pytest.raises(StorageValidationError):
        asyncio.run(adapter.stage(_chunks(*values), max_bytes=max_bytes))
    assert not any(adapter.staging_root.iterdir())


def test_local_storage_rejects_paths_and_symlink_objects(tmp_path: Path) -> None:
    adapter = LocalFilesystemStorageAdapter(tmp_path)
    with pytest.raises(StorageError):
        list(adapter.read("../../secret"))
    target = tmp_path / "outside"
    target.write_bytes(b"secret")
    link = adapter.object_root / ("object-" + "a" * 32)
    link.symlink_to(target)
    with pytest.raises(StorageError):
        list(adapter.read(link.name))
