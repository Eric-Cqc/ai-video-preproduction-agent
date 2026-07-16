# Creative concept and script foundation plan

Status: complete — Stage 11 adds scoped PostgreSQL persistence, deterministic fake-provider generation, idempotent operation reservations, human concept selection, ScriptVersion lineage, tenant-safe APIs, and regression coverage. It deliberately does not add storyboard, shot-plan, media, approval, or real-provider behavior.

## Frozen decisions

- Concepts and scripts are immutable, offline fake-provider candidates pinned to a specific BriefVersion.
- A concept selection is an explicit, one-per-run human decision; only its selected candidate can supply a ScriptVersion.
- Canonical JSON Schema owns validation in Python and TypeScript. Prompts and raw provider output are not persisted or audited.

## Milestones

- [x] A — contracts, ADRs, offline threat model and data plan.
- [x] B — immutable concept/script schema, migration and repositories.
- [x] C — deterministic generation/selection services and idempotency.
- [x] D — tenant-safe APIs and PostgreSQL tests.
- [x] E — regression, documentation and final review.

## Re-evaluation triggers

Review before real provider use, automatic selection, script approval, collaborative editing, retry queues, or cost/token telemetry.
