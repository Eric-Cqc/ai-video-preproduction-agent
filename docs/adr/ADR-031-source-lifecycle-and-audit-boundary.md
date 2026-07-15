# ADR-031: Source lifecycle and audit boundary

- Status: accepted (sixth milestone)

## Decision

Create, version and archive source mutations require the existing roles and atomic audit append. Audit metadata is bounded and excludes checksums, filenames, source references, request payloads and idempotency keys. Repository methods remain tenant-scoped and the UoW remains the sole commit/rollback owner.

Each accepted source operation records both its SourceAsset and immutable SourceAssetVersion, including archive. `reserved` is transaction-local only; failure of pointer CAS, operation finalize or audit rolls back the reservation and all mutation rows. A Brief ingestion with attachments writes one bounded attachment-summary audit event in the same transaction as its normal ingestion-accepted event.
