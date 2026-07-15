# ADR-031: Source lifecycle and audit boundary

- Status: accepted (sixth milestone)

## Decision

Create, version and archive source mutations require the existing roles and atomic audit append. Audit metadata is bounded and excludes checksums, filenames, source references, request payloads and idempotency keys. Repository methods remain tenant-scoped and the UoW remains the sole commit/rollback owner.
