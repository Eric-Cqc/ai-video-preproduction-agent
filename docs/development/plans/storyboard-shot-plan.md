# Storyboard and shot plan foundation plan

Status: Stage 12 complete for submission review — immutable persistence, deterministic offline provider, generation services, tenant-safe APIs, contract parity, PostgreSQL concurrency/rollback tests and full gates are implemented. No image, video, external provider, background job, or UI scope is introduced.

## Frozen decisions

- Storyboard and ShotPlan are immutable structured candidates pinned to ScriptVersion and selected Concept lineage.
- Generation prompts are inert structured data for a future provider; this stage never executes or forwards them.
- Sequence, parent references, duration tolerances and prompt-safety rules reject invalid output rather than repairing it.

## Milestones

- [x] A — contracts, ADRs, safety limits and lineage plan.
- [x] B — immutable data model, migration and validation.
- [x] C — PostgreSQL idempotency, repositories, Unit of Work wiring, deterministic generation and semantic validation.
- [x] D — tenant-safe APIs, replay semantics and transactional/concurrency tests.
- [x] E — migration/full regression, contract parity and security review.

## Stage 12 boundaries

Storyboard and Shot Plan are immutable structured planning artifacts pinned to the
complete upstream lineage. The only provider implementation in this milestone is
the deterministic offline fixture provider with bounded test modes. Provider output
is parsed strictly, validated against the shared schema, then checked for scene,
shot, duration, continuity and prompt-safety semantics; invalid output is rejected
without repair. Request digests include tenant scope, pinned input lineage, template,
provider/model, bounded mode and schema version, while idempotency keys remain
outside the digest. Accepted replay is resolved before lifecycle checks and all
artifact, operation and bounded AuditEvent writes share one Unit of Work commit.

The milestone deliberately excludes real model providers or SDKs, network access,
credentials, image/video generation, media rendering, background jobs/queues,
customer-facing UI, editable boards, cloud storage and Stage 13 work. This is a
deterministic persistence and contract milestone, not a claim of real AI quality.

## Re-evaluation triggers

Review before image/video generation, editable boards, production scheduling, or any Provider dispatch.
