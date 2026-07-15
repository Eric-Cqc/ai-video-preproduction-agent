# Controlled source asset intake plan

- Status: Milestone E complete; no dependencies or lockfile changes, no commit or push.
- Scope: tenant- and Project-scoped metadata identity only. No bytes, storage, upload, parsing, OCR, URL retrieval, AI, Provider, Job, queue, or UI.

## Frozen implementation choices

1. `SourceAsset` is a stable aggregate with `active`/`archived` lifecycle and a database-CAS current-version pointer. `SourceAssetVersion` is immutable after insert.
2. SHA-256 is the only declared checksum; it is syntactically validated but not verified against bytes because this boundary receives no bytes.
3. Metadata is bounded: declared byte size is 1 through 104,857,600; document media types exclude images; filename and provenance are display/opaque metadata only.
4. Source mutations reuse the existing scoped PostgreSQL reservation/finalize pattern in a bounded source-operation record. There is no generic idempotency framework.
5. Accepted Brief ingestion may attach ordered, tenant/Project-scoped SourceAssetVersions through one immutable relation. The attachment list contributes to the existing ingestion digest.
6. The accepted-only attachment rule is enforced by a repository conditional insert against an accepted ingestion row; it is not represented by an unsafe cross-table PostgreSQL CHECK. Finalize, attachment insert and audit remain one UoW transaction.
7. Every accepted SourceAsset operation, including archive, records both the aggregate and its immutable current Version. Revision `f1a2b3c4d5e6` tightened the outcome CHECK after the first implementation exposed that replay requires both identifiers.

## Milestones

### A — governance and model

- [x] Inspect branch, clean worktree, migration head, lockfiles, existing bounded ingestion and transaction model.
- [x] Identify no dependency need or conflict with frozen prior ADRs.
- [x] Add ADR-027 through ADR-031 and complete implementation-ready model review.

### B — persistence boundary

- [x] Add domain validation, migration, SQLAlchemy metadata and migration checks.
- [x] Prove composite ownership, immutable versions, checksum/media/size checks and current pointer constraints in PostgreSQL.

### C — services and idempotency

- [x] Add tenant-scoped repositories/UoW ports and source mutation reservation/finalize operations.
- [x] Add CAS, replay and rollback behavior without repository commit/rollback.

### D — API and Brief linkage

- [x] Add bounded SourceAsset APIs and optional ordered Brief ingestion attachments.
- [x] Keep opaque 404, restricted roles, bounded responses and safe errors.

### E — verification and documentation

- [x] Add real PostgreSQL constraint/concurrency/transaction/isolation tests; update docs and run all gates.
- [x] Validate downgrade/re-upgrade and empty PostgreSQL base → head; metadata drift remains empty.

## Reassessment triggers

File bytes, verification, external retrieval, image support, rejected-outcome retention, real authentication, asynchronous intake, storage, or content extraction each require a separate ADR and explicit approval.
