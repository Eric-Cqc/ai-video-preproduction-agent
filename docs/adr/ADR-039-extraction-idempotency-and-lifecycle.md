# ADR-039: Extraction idempotency and lifecycle

Status: Accepted for Stage 8

## Decision

Use PostgreSQL scoped reservation for extraction requests. The digest covers target source version, verified source checksum, parser identifier/version and fixed options. Accepted replay precedes current SourceAsset lifecycle checks; a new extraction on an archived asset is rejected. Extraction artifact, accepted operation and bounded AuditEvent commit in one UoW.

## Re-evaluation triggers

Review if parsing becomes asynchronous, retryable background work or supports caller-selected safe options.
