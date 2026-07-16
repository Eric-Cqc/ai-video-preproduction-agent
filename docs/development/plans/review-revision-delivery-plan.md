# Stage 13 — Review, Revision and Delivery

Status: Stage 13 complete for local delivery review on `feat/review-revision-delivery`; migration head `a1b2c3d4e5f6`.

## Frozen decisions

- Reviews pin immutable ScriptVersion, StoryboardVersion, ShotPlanVersion, or the exact three-version planning bundle. A review never mutates an artifact.
- Outcomes are `approved`, `revision_requested`, or `rejected`; `reserved` is internal operation state only.
- A revision request is immutable input. Completion creates a new immutable successor artifact and records the predecessor relationship in one lineage table.
- Delivery packages require an approved review for the exact Script/Storyboard/Shot Plan lineage and persist a canonical manifest digest.
- Exports are deterministic local JSON, CSV, README and ZIP data products. Existing local StoragePort is used with opaque immutable keys and compensating deletion on database failure.
- All mutations use scoped PostgreSQL reservation/CAS and append bounded AuditEvent data in the same UoW.

## Scope

Review scope is Script, Storyboard, Shot Plan, or an exact planning bundle. Revision uses deterministic local transformations only; no real provider, image/video generation, rendering, jobs, queues, UI, cloud storage, or Stage 14 scope is included.

## Validation and lineage

Successors preserve the complete upstream lineage, point to the source through `planning_artifact_revision_links`, increment the artifact version number, and receive a fresh canonical content digest. Schema and semantic validators run before persistence. Old artifacts remain readable and immutable; a package must reject mixed or stale lineage.

## API and permissions

Mutation is allowed for owner/admin/member and denied to viewer. Reads are tenant/workspace/project scoped for all roles. Inaccessible resources use opaque 404s. Requests forbid extra fields and client-controlled status, digest, operation, storage key, filename, path, provider endpoint, and tenant body fields. First success is 201, accepted replay is 200, and changed digest is 409.

## Test matrix

PostgreSQL constraints, scoped repositories, review/revision/package/export services, deterministic manifests, safe ZIP/storage behavior, permissions, opaque 404s, same-key concurrency, changed-digest conflicts, winner rollback/takeover, CAS and Audit rollback, compensation cleanup, migration downgrade/re-upgrade, empty base-to-head, and metadata drift.

## Re-evaluation triggers

Review before production providers, remote object storage, PDF generation requiring new dependencies, background delivery jobs, editable UI, or any Stage 14 workflow engine.
