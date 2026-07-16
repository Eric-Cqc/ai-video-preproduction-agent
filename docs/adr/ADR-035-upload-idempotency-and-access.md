# ADR-035: Upload idempotency and access

Status: Accepted for Stage 7

## Decision

Upload operations use a PostgreSQL-scoped unique key over organization, workspace, project, operation, and `Idempotency-Key`. The digest includes the target asset/version plus observed checksum and size. `INSERT ... ON CONFLICT DO NOTHING RETURNING` selects the winner; accepted same-digest requests replay, different-digest requests return 409, and internal `reserved` state is never a success response.

Authorization is checked before streaming and rechecked in the mutation UoW. Reads are fully tenant/Project/asset/version scoped and return opaque 404 for inaccessible resources. Audit contains only object/asset/version identifiers, verified size, and adapter identifier; it excludes bytes, filename, checksum, key, path, and headers.

## Re-evaluation triggers

Review when direct-to-storage upload sessions, resumable chunks, content scanning, or cross-region replication are introduced.
