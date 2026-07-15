# ADR-029: Source metadata and provenance limits

- Status: accepted (sixth milestone)

## Decision

Only a narrow document media-type allowlist and declared size up to 100 MiB are accepted. Filenames are display metadata, never paths. Provenance is bounded opaque metadata; paths, credential-like strings, database URLs, control characters and signed URLs are rejected and never fetched.

The declared 100 MiB limit and declared SHA-256 are validation limits for client-supplied metadata, not evidence that any file exists or has been inspected. A normal resource response may show declared checksum metadata; AuditEvent must not.
