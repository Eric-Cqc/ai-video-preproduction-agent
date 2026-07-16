# ADR-059 — Immutable Revision Successors

Status: Accepted for Stage 13

Completing a revision request creates a new immutable successor run and
version for each requested artifact. Composite tenant lineage and an explicit
ArtifactRevisionLink preserve predecessor, successor and revision-request
identity. Predecessor rows, including all persisted metadata and content,
remain unchanged. Schema and semantic validation occurs before operation
finalization; invalid deterministic output rolls back the complete transaction.
