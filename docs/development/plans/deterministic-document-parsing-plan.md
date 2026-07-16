# Deterministic document parsing plan

Status: completed and validated (Stage 8)

## Scope and dependency decision

Parse verified immutable SourceObject bytes synchronously into an immutable, bounded DocumentExtraction. Standard-library adapters support `text/plain`, `text/csv`, and `application/json`. PDF, DOCX, and XLSX remain explicitly unsupported because no approved reliable parser is locked. No dependency or lockfile change is allowed.

## Frozen decisions

- Parser selection is server-controlled by the verified SourceAssetVersion media type; clients cannot name or load a parser.
- A ParserPort returns canonical `ExtractedDocument` schema v1. Parser identifier/version, source checksum, options digest and extraction checksum are persisted.
- Input is read through StoragePort with a 5 MiB hard cap; normalized output is capped at 1 MiB/characters. This bounded accumulation is required for JSON/CSV canonicalization and is not an unbounded whole-file read.
- UTF-8/UTF-8 BOM only; normalize CRLF/CR to LF; reject NUL/disallowed control characters and invalid encoding.
- CSV is capped at 10,000 rows and 100 columns. JSON is capped at depth 32 and 100,000 nodes, rejects duplicate keys, and canonicalizes sorted compact JSON.
- PostgreSQL reservation owns idempotency. Extraction, accepted outcome, and bounded audit share one UoW commit; repositories never commit/rollback.
- New extraction of an archived SourceAsset is rejected, while accepted replay and reads of an existing extraction remain valid.

## Threat model

Reject binary masquerading as text, decompression/macro/script execution, dynamic parser names, external entity/URL fetch, excessive input/output, deep/wide JSON, large CSV dimensions, duplicate JSON keys and cross-tenant object access. Audit excludes source text, extracted text, filenames, checksums, storage keys and operation keys.

## Milestones

- A — plan, ADR-036 through ADR-039, limits and migration proposal.
- B — parser domain/ports/adapters, migration/metadata and constraint tests.
- C — scoped repositories/UoW and PostgreSQL idempotency.
- D — application/API, safe errors and integration tests.
- E — docs, migration/full gates, staged diff and independent report.

## Replaceable assumptions and triggers

Synchronous standard-library parsing is replaceable. Review when PDF/DOCX/XLSX support is approved, OCR is required, verified inputs exceed 5 MiB, synchronous latency misses an SLO, parser sandboxing is required, or a queue is separately approved.
