# Current project handoff

Generated: 2026-07-17 Asia/Hong_Kong.

## Repository state

- Repository: `ai-video-preproduction-agent`
- Branch: `main`
- Base: `cbdfb49`
- Merge commit / current HEAD: `7890bcb`
- Productization feature HEAD: `893fedf`
- Final documentation reconciliation commit: `893fedf`
- Alembic migration head: `a1b2c3d4e5f6`
- Working tree at handoff: clean
- Merge status: productization was merged through PR #11; no further branch push or PR is pending

The historical Source Asset handoff is archived at
[source-asset-handoff.md](archive/source-asset-handoff.md). It is historical context only and
contains no current instructions.

## Productization commits

1. `3364a5e feat: add product workspace interface`
2. `855ace8 feat: add deterministic end-to-end demo`
3. `2c60f01 chore: harden reliability accessibility and security`
4. `d7d3be1 feat: add provider integration readiness boundary`
5. `8199b61 feat: complete interactive golden path`
6. `9180b4f chore: prepare local release candidate`
7. `eedd194 chore: complete whole-repository release audit`
8. `893fedf docs: reconcile productization release state`

## Current product capability

The tenant-aware Production Desk executes the real local HTTP workflow through application
services, repositories, Unit of Work, PostgreSQL, local StoragePort, human review boundaries and
deterministic offline providers:

```text
Project → Upload → Parse → Brief → Concepts → Script → Storyboard → Shot Plan
→ Review → Delivery → ZIP
```

The path includes SourceAsset registration and verified upload, DocumentExtraction, Brief
candidate acceptance, explicit Concept selection, immutable Script/Storyboard/Shot Plan versions,
exact planning-bundle approval, immutable DeliveryPackageVersion, server-generated export and ZIP
checksum verification. It does not write final business state through SQL or repository shortcuts.

## Local release candidate

The supported local RC commands are:

```bash
make rc-up
make rc-seed
make rc-smoke
make rc-check
make rc-down
make demo-smoke
```

`rc-seed` creates only repeatable local Organization/Workspace context. `rc-smoke` exercises the
complete workflow through real HTTP, PostgreSQL and local storage and verifies representative
replay, changed-digest conflict, exact lineage, permissions, opaque cross-tenant download denial,
ZIP members, manifest and checksum. `rc-down` stops the environment without deleting persistent
volumes.

## Verification record

- Python: 353 tests collected and passed in the full gate.
- Cross-language contracts: 13 tests passed.
- Web: 13 tests passed.
- `make check`: passed, including format, lint, strict types, tests, contract checks, production
  Web build, migration head and metadata-drift checks.
- `make demo-smoke`: passed.
- `make rc-smoke`: passed.
- `make rc-check`: passed.
- Empty database base-to-head and Stage 12/13 boundary downgrade/re-upgrade: passed.
- Final branch diff check: clean.

## Current boundaries and limitations

- Providers are deterministic and offline only; there is no real AI Provider or Provider SDK.
- The release candidate is local only; there is no cloud deployment or cloud object storage.
- There are no jobs, queues, image generation, video generation or media rendering capabilities.
- Temporary local tenant headers are development context, not production authentication.
- The dependency-owned Starlette TestClient deprecation warning remains because resolving it
  requires a prohibited dependency and lockfile change.

## Next actions

Only post-merge product review and future product decisions remain:

1. Perform a manual local product experience pass.
2. Use a new ADR and explicit approval before any future production-capability decision.

Do not resume Stage 13, the historical Source Asset Milestone D, or speculative Stage 20 work from
this handoff.
