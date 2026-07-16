# Binary upload and storage boundary plan

Status: completed and validated (Stage 7)

## Authority and scope

This plan implements the binary boundary authorized after ADR-027 through ADR-031. It preserves the product scope in `FOUNDATION.md`: bytes are source material for preproduction, never an automatic finished-video pipeline. No parser, OCR, model, prompt, provider, queue, UI, cloud storage, or new dependency is included.

## Frozen decisions

- Uploads attach to an existing immutable `SourceAssetVersion`; its declared SHA-256, byte size, and media type are the comparison baseline.
- The transport is a bounded `application/octet-stream` request. Multipart is deferred because the approved dependency set has no multipart parser.
- `StoragePort` owns opaque keys and immutable stage/finalize/read/delete operations. Clients never supply paths or object keys.
- Local/test/ci use a repository-configured local-filesystem adapter. Other environments fail closed until an explicitly reviewed production adapter exists.
- SHA-256 and byte count are computed incrementally while streaming. The request body is never accumulated in memory.
- Upload idempotency uses PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING`; repositories never commit or roll back and the UoW remains the database transaction owner.
- Only an `available` object can be read. Object metadata and accepted upload outcome are tenant, Workspace, Project, SourceAsset, and SourceAssetVersion scoped.

## Storage/database transaction gap

True distributed atomicity is impossible between PostgreSQL and a filesystem/object store. The ordered protocol is: authorize; stage and verify bytes; reserve the scoped operation; finalize to a non-overwritable opaque key; insert available metadata, accept the operation, append bounded audit, and commit once. A losing replay deletes its private stage. If the database transaction fails after finalize, the service deletes the final object. If compensation deletion fails, a separate bounded cleanup requirement is recorded after rollback; the API still reports failure. No database success is committed before storage finalize.

## Threat model

- Path traversal and symlink escape: no client path participates in storage addressing; resolved paths must remain below configured roots; exclusive creation and no-follow checks are used.
- Resource exhaustion: `Content-Length` is prechecked when present and the streaming counter enforces the same limit when absent or false.
- Content substitution: observed byte count and SHA-256 must exactly equal immutable declared metadata.
- Tenant bypass: every repository query and API read includes organization, workspace, project, asset, and version scope; inaccessible resources are opaque 404.
- Overwrite/race: random staging and final keys use exclusive creation; finalization never replaces an existing object; one available object per SourceAssetVersion is database-enforced.
- Sensitive leakage: payload bytes, idempotency keys, filenames, checksums, paths, database errors, and request headers are absent from audit and public errors.
- Crash residue: unreferenced staging/final objects are an acknowledged operational risk; bounded cleanup records and later reconciliation are the extension point.

## Milestones

- A — plan, threat model, dependency decision, ADR-032 through ADR-035.
- B — migration, domain records, storage port/local adapter, repositories and UoW.
- C — upload application service, compensation, replay, scoped read.
- D — API, configuration, request limits, tests for bytes/security/transactions/concurrency.
- E — docs, migration round trip/drift, full quality gates, staged diff and security review.

## Replaceable assumptions

- The local filesystem is a development adapter, not the production storage selection.
- Raw octet-stream transport may be replaced by multipart or direct-to-storage protocols after dependency and threat review.
- Synchronous in-request upload is acceptable up to the existing 100 MiB domain limit for this milestone.

## Re-evaluation triggers

Review when production object storage is selected, upload limits exceed 100 MiB, direct browser upload is proposed, resumable/multipart transfer is required, malware scanning becomes mandatory, or cleanup residue cannot be kept within an operational SLO.

## Dependency decision

No dependency or lockfile change. FastAPI/Starlette request streaming, Python `hashlib`, `pathlib`, and filesystem primitives are sufficient. Multipart, cloud SDKs, and asynchronous storage packages are explicitly deferred.
