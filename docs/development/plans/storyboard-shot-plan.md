# Storyboard and shot plan foundation plan

Status: in progress — canonical contracts and prompt validation exist; persistence, lineage services, APIs, duration checks, and PostgreSQL tests remain pending.

## Frozen decisions

- Storyboard and ShotPlan are immutable structured candidates pinned to ScriptVersion and selected Concept lineage.
- Generation prompts are inert structured data for a future provider; this stage never executes or forwards them.
- Sequence, parent references, duration tolerances and prompt-safety rules reject invalid output rather than repairing it.

## Milestones

- A — contracts, ADRs, safety limits and lineage plan.
- B — immutable data model, migration and validation.
- C — deterministic generation, idempotency and repositories.
- D — tenant-safe APIs and transactional tests.
- E — migration/full regression and security review.

## Re-evaluation triggers

Review before image/video generation, editable boards, production scheduling, or any Provider dispatch.
