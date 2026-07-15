# ADR-028: Source content identity and duplicates

- Status: accepted (sixth milestone)

## Decision

The sole declared checksum is lowercase 64-character SHA-256. A matching declared checksum, media type and byte size is surfaced as duplicate-content metadata only; aggregates are never automatically merged or deduplicated. Mutation idempotency remains tenant/Project/operation/key scoped and uses the existing PostgreSQL reservation pattern.

Duplicate indication is scoped to the same Organization, Workspace and Project. It is not a global checksum lookup and does not expose other tenants' metadata. Replay is resolved from the accepted operation before lifecycle or pointer CAS checks.

## Limitation

No bytes enter this system, so the declared checksum is not verified.
