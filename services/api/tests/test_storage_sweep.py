import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from infra.scripts.storage_sweep import PendingCleanup, SweepResult, sweep_storage

NOW = 1_800_000_000.0
LOCAL_ADAPTER = "local_filesystem_v1"


class _MemoryCleanupStore:
    def __init__(
        self, *, referenced: set[str] | None = None, pending: list[PendingCleanup] | None = None
    ) -> None:
        self.referenced = referenced or set()
        self.pending = pending or []
        self.deleted_rows: list[PendingCleanup] = []

    def referenced_storage_keys(self) -> set[str]:
        return set(self.referenced)

    def pending_cleanup(self) -> list[PendingCleanup]:
        return list(self.pending)

    def delete_cleanup_requirement(self, requirement: PendingCleanup) -> None:
        self.deleted_rows.append(requirement)
        self.pending.remove(requirement)


def _old_file(root: Path, directory: str, key: str) -> Path:
    path = root / directory / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test object")
    os.utime(path, (NOW - 48 * 60 * 60, NOW - 48 * 60 * 60))
    return path


def _sweep(root: Path, store: _MemoryCleanupStore, *, apply: bool) -> SweepResult:
    return sweep_storage(
        root,
        store,
        grace_period=timedelta(hours=24),
        apply=apply,
        now=NOW,
    )


def test_old_unreferenced_file_is_swept(tmp_path: Path) -> None:
    path = _old_file(tmp_path, "objects", "object-" + "a" * 32)

    result = _sweep(tmp_path, _MemoryCleanupStore(), apply=True)

    assert result.deleted_files == 1
    assert not path.exists()


def test_referenced_file_is_protected(tmp_path: Path) -> None:
    key = "object-" + "b" * 32
    path = _old_file(tmp_path, "objects", key)

    result = _sweep(tmp_path, _MemoryCleanupStore(referenced={key}), apply=True)

    assert result.protected_files == 1
    assert path.exists()


def test_dry_run_does_not_delete_candidates_or_cleanup_rows(tmp_path: Path) -> None:
    key = "stage-" + "c" * 32
    path = _old_file(tmp_path, "staging", key)
    candidate_path = _old_file(tmp_path, "objects", "object-" + "f" * 32)
    pending = PendingCleanup("source_object_cleanup_requirements", uuid4(), LOCAL_ADAPTER, key)
    store = _MemoryCleanupStore(pending=[pending])

    result = _sweep(tmp_path, store, apply=False)

    assert result.pending_planned == 1
    assert result.candidate_files == 1
    assert result.deleted_files == 0
    assert store.deleted_rows == []
    assert path.exists()
    assert candidate_path.exists()


def test_rerunning_sweep_after_success_is_idempotent(tmp_path: Path) -> None:
    _old_file(tmp_path, "objects", "object-" + "d" * 32)
    store = _MemoryCleanupStore()

    first = _sweep(tmp_path, store, apply=True)
    second = _sweep(tmp_path, store, apply=True)

    assert first.deleted_files == 1
    assert second.deleted_files == 0
    assert second.failed_deletions == 0


def test_failed_pending_deletion_retains_cleanup_row(tmp_path: Path) -> None:
    key = "object-" + "e" * 32
    path = _old_file(tmp_path, "objects", key)
    pending = PendingCleanup("delivery_export_cleanup_requirements", uuid4(), LOCAL_ADAPTER, key)
    store = _MemoryCleanupStore(pending=[pending])

    def fail_delete(_: Path) -> None:
        raise OSError("injected deletion failure")

    result = sweep_storage(
        tmp_path,
        store,
        grace_period=timedelta(hours=24),
        apply=True,
        now=NOW,
        delete_file=fail_delete,
    )

    assert result.failed_deletions == 1
    assert store.pending == [pending]
    assert path.exists()
