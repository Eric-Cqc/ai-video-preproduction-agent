# Stage 7 binary upload and storage report

## Outcome

Stage 7 is complete with no known must-fix item. It adds a bounded binary boundary without parsing, AI, cloud storage, new dependencies, or lockfile changes.

## Implemented decisions

- Migration head `a7b8c9d0e1f2` adds tenant-scoped `source_objects`, PostgreSQL-idempotent `source_object_uploads`, and bounded `source_object_cleanup_requirements`.
- Uploads target an existing immutable SourceAssetVersion and accept `application/octet-stream` only.
- The local/test/ci filesystem adapter streams to exclusive random staging keys, computes actual SHA-256 and byte size, verifies declared metadata, finalizes without overwrite, and reads only server-generated opaque keys.
- `disabled` is the fail-closed non-storage adapter used when a non-local environment needs the API health/security boundary without enabling object operations.
- Reservation, available metadata, accepted outcome and bounded AuditEvent share one UoW commit. Storage finalize precedes database commit; database failure compensates by deletion, and deletion failure is recorded separately after rollback.
- Accepted same-key/same-byte replay returns the original result; same key/different observed digest returns 409. Concurrent losers do not create another object or audit.
- Object metadata and content reads require full Organization/Workspace/Project/SourceAsset/SourceAssetVersion scope and return opaque 404 when inaccessible.

## Verification

- New revision upgrade, one-revision downgrade/re-upgrade, `alembic current --check-heads`, and metadata drift check passed.
- Storage/API/transaction/concurrency targeted tests passed, including winner rollback takeover, audit rollback, finalize failure, cleanup failure record, traversal, symlink, immutable finalize, restart read, checksum/size mismatch and stream limits.
- Complete `make check` passed: 194 Python tests, 8 contract Vitest tests, 10 Web Vitest tests, 9 contract/integration Python tests, Ruff, mypy, ESLint, TypeScript, contract gates, and Next.js production build.
- `git diff --check` passed. Dependency manifests and lockfiles are unchanged.

## Security observations and accepted limits

- Payload bytes, filenames, checksums, storage keys/paths, Idempotency-Key, headers and database errors are absent from AuditEvent and public responses.
- The local adapter is not a production recommendation and is rejected outside local/test/ci.
- Content-Length and streaming counters do not replace an infrastructure body limit.
- MIME sniffing, malware scanning, retention/encryption policy and production KMS are deferred.
- PostgreSQL and storage have no distributed transaction. Compensation is tested, but a process crash can still leave an orphan object; cleanup reconciliation is the documented extension point.
- The existing Starlette/httpx deprecation warning remains accepted and unrelated to this stage.

## Next stage

Proceed to deterministic synchronous parsing of verified immutable objects with standard-library plain text, CSV and JSON adapters only. PDF, DOCX and XLSX remain explicitly unsupported without separately approved parser dependencies.
