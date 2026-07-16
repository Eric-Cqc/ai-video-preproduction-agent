# Stage 8 deterministic document parsing report

## Outcome

Stage 8 is complete with no known must-fix item. It adds no dependency or lockfile change and does not implement OCR, AI, dynamic plugins, external fetch or background jobs.

## Supported and unsupported formats

- Supported: strict UTF-8/UTF-8-BOM `text/plain`, `text/csv`, and `application/json`.
- Unsupported: PDF, DOCX and XLSX. Their metadata/upload remains valid, but extraction returns a safe unsupported-media error.

## Architecture and determinism

Server-selected ParserPort adapters emit ExtractedDocument schema v1. Plain text normalizes newlines; CSV parses and re-emits deterministic RFC-style rows; JSON rejects duplicate keys/non-finite constants and emits sorted compact JSON. The immutable artifact records parser/version, verified source digest, fixed options digest, extraction digest, counts and bounded structured output. Parser upgrades create new artifacts rather than updates.

## Resource and security limits

Input is bounded to 5 MiB; normalized output to 1 MiB/characters; CSV to 10,000 rows/100 columns; JSON to depth 32/100,000 nodes. Disallowed control bytes and invalid UTF-8 are rejected. Bytes are reread through StoragePort and checksum/size reverified before parsing. No parser executes code/macros, decompresses archives, fetches URLs or selects caller plugins. Audit excludes full source/output text and sensitive storage/idempotency data.

## Persistence, replay and tests

Migration head `b8c9d0e1f2a3` adds immutable tenant-scoped extraction and PostgreSQL reservation tables. Artifact, accepted outcome and audit share one UoW. Same-key accepted replay returns the original artifact without rereading storage or rechecking later archive state; a new extraction on an archived asset is rejected.

Targeted parser/API/transaction/concurrency tests passed, including BOM/newlines, encoding/binary rejection, CSV limits, JSON depth/nodes/duplicates/canonical output, unsupported formats, cross-tenant access, audit rollback, object tampering, concurrent replay and unique parser results. Full validation results are recorded after the stage gate.

## Accepted limits and next stage

Bounded accumulation up to 5 MiB is intentional for deterministic JSON/CSV parsing; larger verified objects are unsupported rather than read without bound. Rich document formats require separately approved parser dependencies and threat review. Next is an offline model-independent Brief extraction foundation with deterministic fake provider only.
