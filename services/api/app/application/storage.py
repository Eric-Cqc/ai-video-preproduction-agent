import hashlib
import os
from collections.abc import AsyncIterable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class StorageError(Exception):
    pass


class StorageValidationError(StorageError):
    pass


@dataclass(frozen=True, slots=True)
class StagedObject:
    storage_key: str
    observed_byte_size: int
    observed_checksum_value: str


class StoragePort(Protocol):
    adapter_name: str

    async def stage(self, chunks: AsyncIterable[bytes], *, max_bytes: int) -> StagedObject: ...

    def new_final_key(self) -> str: ...

    def finalize(self, staging_key: str, final_key: str) -> None: ...

    def delete(self, storage_key: str) -> None: ...

    def read(self, storage_key: str, *, chunk_size: int = 64 * 1024) -> Iterator[bytes]: ...


class LocalFilesystemStorageAdapter:
    adapter_name = "local_filesystem_v1"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.staging_root = self.root / "staging"
        self.object_root = self.root / "objects"
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.object_root.mkdir(parents=True, exist_ok=True)

    async def stage(self, chunks: AsyncIterable[bytes], *, max_bytes: int) -> StagedObject:
        key = f"stage-{uuid4().hex}"
        path = self._path(key, staging=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError as error:
            raise StorageError("unable to create staging object") from error
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, "wb") as output:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise StorageValidationError("upload exceeds the allowed byte limit")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size == 0:
                raise StorageValidationError("empty uploads are not allowed")
        except BaseException:
            with suppress(OSError):
                path.unlink(missing_ok=True)
            raise
        return StagedObject(key, size, digest.hexdigest())

    def new_final_key(self) -> str:
        return f"object-{uuid4().hex}"

    def finalize(self, staging_key: str, final_key: str) -> None:
        source = self._path(staging_key, staging=True)
        target = self._path(final_key, staging=False)
        try:
            os.link(source, target, follow_symlinks=False)
        except FileExistsError as error:
            raise StorageError("immutable object key already exists") from error
        except OSError as error:
            raise StorageError("unable to finalize immutable object") from error
        try:
            os.chmod(target, 0o400, follow_symlinks=False)
            source.unlink()
        except OSError as error:
            target.unlink(missing_ok=True)
            raise StorageError("unable to finalize immutable object") from error

    def delete(self, storage_key: str) -> None:
        try:
            path = self._path(storage_key, staging=storage_key.startswith("stage-"))
            if path.exists():
                os.chmod(path, 0o600, follow_symlinks=False)
            path.unlink(missing_ok=True)
        except OSError as error:
            raise StorageError("unable to delete stored object") from error

    def read(self, storage_key: str, *, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        path = self._path(storage_key, staging=False)
        if path.is_symlink() or not path.is_file():
            raise StorageError("stored object is unavailable")
        try:
            with path.open("rb") as source:
                while chunk := source.read(chunk_size):
                    yield chunk
        except OSError as error:
            raise StorageError("stored object is unavailable") from error

    def _path(self, key: str, *, staging: bool) -> Path:
        expected_prefix = "stage-" if staging else "object-"
        suffix = key.removeprefix(expected_prefix)
        if not key.startswith(expected_prefix) or len(suffix) != 32 or not suffix.isalnum():
            raise StorageError("invalid opaque storage key")
        parent = self.staging_root if staging else self.object_root
        path = parent / key
        if path.parent.resolve() != parent.resolve():
            raise StorageError("storage path escapes configured root")
        return path


class DisabledStorageAdapter:
    adapter_name = "disabled"

    async def stage(self, chunks: AsyncIterable[bytes], *, max_bytes: int) -> StagedObject:
        del chunks, max_bytes
        raise StorageError("object storage is disabled")

    def new_final_key(self) -> str:
        raise StorageError("object storage is disabled")

    def finalize(self, staging_key: str, final_key: str) -> None:
        del staging_key, final_key
        raise StorageError("object storage is disabled")

    def delete(self, storage_key: str) -> None:
        del storage_key
        raise StorageError("object storage is disabled")

    def read(self, storage_key: str, *, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        del storage_key, chunk_size
        raise StorageError("object storage is disabled")
        yield b""  # pragma: no cover
