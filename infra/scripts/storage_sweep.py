"""Safely sweep old unreferenced local object-storage files."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import Engine, create_engine, text

LOCAL_STORAGE_ADAPTER = "local_filesystem_v1"
_KEY_PATTERN = re.compile(r"^(?:object|stage)-[A-Za-z0-9]{32}$")
_CLEANUP_TABLES = {
    "source_object_cleanup_requirements": "source_object_cleanup_requirements",
    "delivery_export_cleanup_requirements": "delivery_export_cleanup_requirements",
}


@dataclass(frozen=True, slots=True)
class PendingCleanup:
    table_name: str
    id: UUID
    storage_adapter: str
    storage_key: str


class CleanupStore(Protocol):
    def referenced_storage_keys(self) -> set[str]: ...

    def pending_cleanup(self) -> list[PendingCleanup]: ...

    def delete_cleanup_requirement(self, requirement: PendingCleanup) -> None: ...


class SqlAlchemyCleanupStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def referenced_storage_keys(self) -> set[str]:
        with self.engine.connect() as connection:
            return {
                str(storage_key)
                for storage_key in connection.scalars(
                    text(
                        "SELECT storage_key FROM source_objects "
                        "UNION "
                        "SELECT storage_key FROM delivery_export_files"
                    )
                )
            }

    def pending_cleanup(self) -> list[PendingCleanup]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT table_name, id, storage_adapter, storage_key "
                    "FROM ("
                    "SELECT 'source_object_cleanup_requirements' AS table_name, id, "
                    "storage_adapter, storage_key, created_at "
                    "FROM source_object_cleanup_requirements "
                    "UNION ALL "
                    "SELECT 'delivery_export_cleanup_requirements' AS table_name, id, "
                    "storage_adapter, storage_key, created_at "
                    "FROM delivery_export_cleanup_requirements"
                    ") AS cleanup "
                    "ORDER BY created_at, id"
                )
            ).mappings()
            return [
                PendingCleanup(
                    table_name=str(row["table_name"]),
                    id=cast(UUID, row["id"]),
                    storage_adapter=str(row["storage_adapter"]),
                    storage_key=str(row["storage_key"]),
                )
                for row in rows
            ]

    def delete_cleanup_requirement(self, requirement: PendingCleanup) -> None:
        table_name = _CLEANUP_TABLES.get(requirement.table_name)
        if table_name is None:
            raise ValueError("unknown cleanup table")
        with self.engine.begin() as connection:
            connection.execute(
                text(f"DELETE FROM {table_name} WHERE id = :id"),
                {"id": requirement.id},
            )


@dataclass(frozen=True, slots=True)
class SweepResult:
    pending_seen: int
    pending_planned: int
    pending_deleted: int
    pending_protected: int
    candidate_files: int
    fresh_files: int
    protected_files: int
    deleted_files: int
    failed_deletions: int


def _path_for_key(root: Path, storage_key: str) -> Path | None:
    if _KEY_PATTERN.fullmatch(storage_key) is None:
        return None
    parent = root / ("staging" if storage_key.startswith("stage-") else "objects")
    if parent.is_symlink():
        return None
    path = parent / storage_key
    if path.parent.resolve() != parent.resolve():
        return None
    return path


def _iter_candidate_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for directory, prefix in ((root / "objects", "object-"), (root / "staging", "stage-")):
        if directory.is_symlink():
            continue
        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except FileNotFoundError:
            continue
        for entry in entries:
            if (
                entry.name.startswith(prefix)
                and _KEY_PATTERN.fullmatch(entry.name) is not None
                and not entry.is_symlink()
                and entry.is_file()
            ):
                candidates.append(entry)
    return candidates


def _unlink_idempotently(path: Path) -> None:
    path.unlink(missing_ok=True)


def sweep_storage(
    root: Path,
    store: CleanupStore,
    *,
    grace_period: timedelta,
    apply: bool,
    now: float,
    delete_file: Callable[[Path], None] = _unlink_idempotently,
    storage_adapter: str = LOCAL_STORAGE_ADAPTER,
) -> SweepResult:
    if grace_period.total_seconds() < 0:
        raise ValueError("grace period cannot be negative")
    root = root.resolve()
    pending_rows = store.pending_cleanup()
    protected_keys = store.referenced_storage_keys()
    pending_keys = {row.storage_key for row in pending_rows}
    pending_planned = 0
    pending_deleted = 0
    pending_protected = 0
    failed_deletions = 0

    for requirement in pending_rows:
        if requirement.storage_adapter != storage_adapter:
            failed_deletions += 1
            continue
        if requirement.storage_key in protected_keys:
            pending_protected += 1
            continue
        path = _path_for_key(root, requirement.storage_key)
        if path is None:
            failed_deletions += 1
            continue
        if not apply:
            pending_planned += 1
            continue
        try:
            delete_file(path)
            store.delete_cleanup_requirement(requirement)
        except Exception:
            failed_deletions += 1
        else:
            pending_deleted += 1

    cutoff = now - grace_period.total_seconds()
    candidate_files = 0
    fresh_files = 0
    protected_files = 0
    deleted_files = 0
    for path in _iter_candidate_files(root):
        if path.name in pending_keys:
            continue
        if path.name in protected_keys:
            protected_files += 1
            continue
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            failed_deletions += 1
            continue
        if modified_at > cutoff:
            fresh_files += 1
            continue
        candidate_files += 1
        if not apply:
            continue
        try:
            delete_file(path)
        except Exception:
            failed_deletions += 1
        else:
            deleted_files += 1

    return SweepResult(
        pending_seen=len(pending_rows),
        pending_planned=pending_planned,
        pending_deleted=pending_deleted,
        pending_protected=pending_protected,
        candidate_files=candidate_files,
        fresh_files=fresh_files,
        protected_files=protected_files,
        deleted_files=deleted_files,
        failed_deletions=failed_deletions,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete eligible files and rows")
    parser.add_argument(
        "--grace-hours",
        "--grace-period-hours",
        dest="grace_hours",
        type=float,
        default=24.0,
        help="age threshold for files, in hours (default: 24)",
    )
    parser.add_argument(
        "--storage-root",
        default=os.environ.get("SOURCE_OBJECT_STORAGE_ROOT", ".local/source-objects"),
    )
    parser.add_argument(
        "--storage-adapter",
        default=os.environ.get("SOURCE_OBJECT_STORAGE_ADAPTER", LOCAL_STORAGE_ADAPTER),
    )
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    return parser


def _print_result(result: SweepResult, *, apply: bool, grace_hours: float) -> None:
    mode = "apply" if apply else "dry-run"
    print(
        "storage-sweep "
        f"mode={mode} grace_hours={grace_hours:g} "
        f"pending_seen={result.pending_seen} pending_planned={result.pending_planned} "
        f"pending_deleted={result.pending_deleted} pending_protected={result.pending_protected} "
        f"candidates={result.candidate_files} fresh={result.fresh_files} "
        f"protected={result.protected_files} deleted={result.deleted_files} "
        f"failed={result.failed_deletions}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.grace_hours < 0:
        print("storage-sweep error=negative_grace_period", file=sys.stderr)
        return 2
    if args.storage_adapter != LOCAL_STORAGE_ADAPTER:
        print("storage-sweep error=local_adapter_required", file=sys.stderr)
        return 2
    if not args.database_url:
        print("storage-sweep error=database_url_required", file=sys.stderr)
        return 2

    engine = create_engine(args.database_url, pool_pre_ping=True)
    try:
        result = sweep_storage(
            Path(args.storage_root),
            SqlAlchemyCleanupStore(engine),
            grace_period=timedelta(hours=args.grace_hours),
            apply=args.apply,
            now=time.time(),
            storage_adapter=args.storage_adapter,
        )
    except Exception:
        print("storage-sweep error=sweep_failed", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    _print_result(result, apply=args.apply, grace_hours=args.grace_hours)
    return 1 if result.failed_deletions else 0


if __name__ == "__main__":
    raise SystemExit(main())
