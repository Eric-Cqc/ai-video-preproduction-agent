# ADR-030: Source asset attachment to Brief ingestion

- Status: accepted (sixth milestone)

## Decision

Accepted Brief ingestion may attach ordered SourceAssetVersions through one immutable, tenant/Project-scoped relation. Attachment validation and rows share the ingestion transaction. The ordered IDs and relation types contribute to the ingestion digest; replay writes no duplicate attachment.

Positions are zero-based, unique within an ingestion and provide deterministic retrieval order. At most ten attachment inputs are accepted. PostgreSQL cannot safely express the cross-table accepted-status predicate as a CHECK, so the attachment repository uses a conditional insert whose source ingestion must already be `accepted`; finalize, conditional insert and audit stay in the same UoW transaction. An accepted replay reads its committed rows without revalidating a later SourceAsset archive state.
