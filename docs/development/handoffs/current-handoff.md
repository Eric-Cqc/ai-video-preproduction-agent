# Current project handoff

Generated: 2026-08-15 Asia/Shanghai. Updated for Stage 21.

## Repository state

- Repository: `ai-video-preproduction-agent`
- Branch: `main`
- Stage 20 (`2267cd9`, truthful Local RC) is committed and pushed to
  `Eric-Cqc/ai-video-preproduction-agent`.
- Stage 21 (WS-R reliability/operational safety, WS-P adapter truthfulness, WS-V hosted
  validation, WS-D docs) is integrated on top of it in this working tree; commit/push status
  depends on Sol Ultra review outcome and the current session's Final Acceptance decision.
- Alembic migration head: `f0a1b2c3d4e5` (chain: `d5e6f7a8b9c0 → e6f7a8b9c0d1 →
  e9f0a1b2c3d4 → f0a1b2c3d4e5`).
- Expected verification counts: `428` Python, `13` contract, `30` Web tests, plus the production
  Web build.

The historical Source Asset handoff is archived at
[source-asset-handoff.md](archive/source-asset-handoff.md). It is historical context only and
contains no current instructions.

## Current product capability

The tenant-aware Production Desk now exercises the real local HTTP workflow through application
services, repositories, Unit of Work, PostgreSQL, local storage, human review boundaries and
deterministic offline providers:

```text
Project → Upload → Parse → Brief candidate review → Concepts → Script
→ Storyboard → Shot Plan → Bundle approval → Delivery → ZIP
```

Human gates are real in the UI: a user explicitly accepts or rejects the Brief candidate, selects
one of three concepts, runs the planning stages as visible actions, and approves the planning
bundle or requests changes. The UI reads structured artifacts and retains tenant/project lineage;
the backend still enforces the same immutable and auditable boundaries.

## Local release candidate commands

```bash
make setup
make rc-up
make rc-seed
make rc-golden-path-test
make rc-smoke
make rc-check
make rc-down
```

`rc-golden-path-test` is the in-process regression suite preserved from the previous `rc-smoke`.
`rc-smoke` is now socket-level: it exercises a running API through the complete workflow —
unique tenant bootstrap, replay/conflict, viewer denial, opaque cross-tenant 404, ZIP membership,
manifest, and checksum checks — and verifies the running Web server's health and rendered shell.
It does not drive the browser UI; the interactive human-gate workflow is verified manually
per the release checklist. `rc-check` repeats the socket smoke on isolated ports
`18001/13001`, `foundation_test`, and an isolated storage root, then cleans up its own processes.

## Stage 21: hosted pilot validation and operational hardening

Three parallel Luna Max builders (WS-R backend reliability, WS-P adapter truthfulness, WS-V
hosted validation) plus a docs workstream (WS-D) closed the following, each with real-host
verification (not sandbox-only claims):

- **WS-R**: narrowed three repositories' broad exception handling to `IntegrityError`-only
  (F-18); added a durable `delivery_export_cleanup_requirements` table and delete-or-record
  compensation for export cleanup failures (F-20); added an operator `make storage-sweep`
  command (dry-run by default, no scheduler); fixed a real RC/hosted process-ownership bug where
  `ps`-command-substring matching produced false "unowned PID" refusals once npm renamed its own
  displayed command — replaced with a port-descendant `lsof` check, live-verified via a full
  `rc-up → rc-seed → rc-smoke → rc-down` and `rc-check` cycle with zero leftover processes; added
  a live-verified `make hosted-backup` target.
- **WS-P**: fixed F-27 (configured DeepSeek base URL/model were validated then silently ignored;
  now actually used); persisted provider usage metadata additively; added bounded retry backoff
  and a wall-clock deadline; mapped provider failures to stable error codes; bounded
  `requested_changes` size/depth; moved provider calls for concepts/script/storyboard/shot-plan
  outside open database transactions (F-19), matching the brief-extraction pattern — **the
  revision path was explicitly left inside an open transaction as a documented, out-of-scope
  residual** (bundled up to three calls, all-or-nothing, judged Large effort).
- **WS-V**: removed the full `.env.hosted` injection into the `web` container (least privilege);
  added Web/Caddy healthchecks; replaced the internal-health-only `hosted-smoke` with a real
  proxy-origin smoke (`infra/scripts/hosted_proxy_smoke.py`) exercising the gate, cookie flags,
  the full deterministic Golden Path workflow, replay/409, cross-tenant 404, and ZIP integrity;
  added `make hosted-env-local` for no-key local validation; fixed the pilot rate limiter to key
  on the first `X-Forwarded-For` hop in hosted mode instead of the shared proxy address.
- **WS-D**: landed `docs/hosted/HOSTED_PILOT_REVIEW.md` (the ADR-064-required review record,
  outcome: conditional, live key not accepted), `docs/adr/ADR-067-hosted-pilot-review-outcome.md`,
  and a fully verified `docs/hosted/OPERATIONS_RUNBOOK.md`; reconciled `KNOWN_LIMITATIONS.md`,
  `REAL_PROVIDER_INTEGRATION_CHECKLIST.md`, and `README.md`.

### Integration notes for future maintainers

The three builders ran in separate git worktrees/clones and were merged with real `git merge`
(not blind file copies). Two real regressions were caught and fixed during integration, not by
any single builder's own testing:

1. WS-P's new migration (`f0a1b2c3d4e5`) rewrote the `audit_events` CHECK constraint from a
   baseline string that predated Stage 20's `planning_revision.cancelled` value, silently
   dropping it. This broke revision cancellation (409 `audit_conflict`) and was caught by the
   full integrated `make test` run, not by WS-P's own DB-blocked sandbox tests. Fixed in the
   migration's `_OLD_AUDIT` constant and the equivalent ORM `CheckConstraint` in `models.py` (both
   needed the fix — they must stay in sync, and a repo test
   (`test_failed_generation_constraints_match_failure_migration`) asserts they do).
2. WS-R's RC process-ownership fix (see above) was implemented but could not be live-verified in
   its own sandbox (no Docker/socket access there); it was verified for real on the integration
   host, which is also how the false-positive was originally caught.

## Frozen boundaries and remaining work

- Deterministic offline providers remain the default for Local RC, CI, and tests.
- ADR-064 permits only the opt-in server-side `deepseek-v4-flash` pilot adapter; raw prompts,
  source bodies, keys, and Provider responses are not persisted, audited, logged, or sent to the
  browser.
- ADR-064's required privacy/retention/cost/availability review now has a code-level answer
  (`ADR-067`, conditional). Live-key activation still requires **PRODUCT DECISION** work (external
  Provider contract terms, budget/rate controls, approved data classification) that this
  repository cannot satisfy by itself.
- Live Provider end-to-end validation is **EXTERNAL** work and has not been completed.
- The revision-path provider-call transaction residual (see WS-P above) is a known, documented
  gap for the next hardening pass — not a regression, a deliberately bounded exclusion.
- F-09 (storage finalize before DB commit) has durable cleanup + an operator sweep now, but the
  crash window itself remains the accepted ADR-034 residual.
- The hosted pilot remains private and single-tenant with local-auth/access-gate limits; cloud
  object storage, production multi-tenant identity, queues, media generation, rendering, and
  publishing remain out of scope.

Do not create ADR-065 or reopen frozen exclusions without the required product decision and
evidence.
