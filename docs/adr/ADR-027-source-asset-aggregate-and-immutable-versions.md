# ADR-027: SourceAsset aggregate and immutable versions

- Status: accepted (sixth milestone)

## Decision

`SourceAsset` is a tenant/Project-scoped stable identity with `active` and `archived` only. Every replacement creates a new immutable `SourceAssetVersion`; the aggregate uses a same-asset current pointer and CAS token. Predecessors are never changed.

## Boundary

This records declared metadata and content identity only. It does not receive, retain, parse or verify bytes.
