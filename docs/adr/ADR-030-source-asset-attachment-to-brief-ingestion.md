# ADR-030: Source asset attachment to Brief ingestion

- Status: accepted (sixth milestone)

## Decision

Accepted Brief ingestion may attach ordered SourceAssetVersions through one immutable, tenant/Project-scoped relation. Attachment validation and rows share the ingestion transaction. The ordered IDs and relation types contribute to the ingestion digest; replay writes no duplicate attachment.
