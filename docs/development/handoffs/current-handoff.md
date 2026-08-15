# Current project handoff

Generated: 2026-08-15 Asia/Shanghai.

## Repository state

- Repository: `ai-video-preproduction-agent`
- Branch: `main`
- Base/current commit: `main@79209e4`
- Stage-20 WS-A (A1–A7), WS-B (human-gate Production Desk), and WS-C are uncommitted in this
  working tree.
- Alembic migration head: `d5e6f7a8b9c0`
- Expected verification counts: `395` Python, `13` contract, `30` Web tests, plus the production
  Web build.
- No commit or push is part of this handoff.

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

## Verification record

- Integrated Stage-20 baseline counts: `395` Python / `13` contract / `30` Web tests and the
  production Web build.
- Full database-backed verification was re-run on the host after integration: `make check`
  passed (395 Python / 13 contract / 30 Web tests, production Web build), `make rc-check`
  passed its isolated socket cycle, and a downgrade/upgrade cycle across the three new
  migrations succeeded on `foundation_test`.
- The empty-port check after the RC cycles (`lsof -i :18000 -i :13000 -i :18001 -i :13001`)
  returned no entries.

## Frozen boundaries and remaining work

- Deterministic offline providers remain the default for Local RC, CI, and tests.
- ADR-064 permits only the opt-in server-side `deepseek-v4-flash` pilot adapter; raw prompts,
  source bodies, keys, and Provider responses are not persisted, audited, logged, or sent to the
  browser.
- ADR-064 privacy/retention/cost/availability review is **PRODUCT DECISION** work and has not been
  completed.
- Live Provider end-to-end validation is **EXTERNAL** work and has not been completed.
- The hosted pilot remains private and single-tenant with local-auth/access-gate limits; cloud
  object storage, production multi-tenant identity, queues, media generation, rendering, and
  publishing remain out of scope.
- F-09 remains the accepted ADR-034 storage-finalize-before-DB-commit residual; its post-stage
  owner is next stage planning.

Do not create ADR-065 or reopen frozen Stage-20 exclusions without the required product decision
and evidence.
