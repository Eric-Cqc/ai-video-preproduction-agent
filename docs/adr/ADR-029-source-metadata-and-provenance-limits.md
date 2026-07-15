# ADR-029: Source metadata and provenance limits

- Status: accepted (sixth milestone)

## Decision

Only a narrow document media-type allowlist and declared size up to 100 MiB are accepted. Filenames are display metadata, never paths. Provenance is bounded opaque metadata; paths, credential-like strings, database URLs, control characters and signed URLs are rejected and never fetched.
