# Archived Source Asset handoff

> Archived on 2026-07-17. This document preserves historical milestone context and must not be
> used as current branch, scope, status, or next-step instructions. See
> [current-handoff.md](../current-handoff.md) for the authoritative state.

> Authoritative current state (2026-07-17): Stages 1–13 are complete and merged.
> Stages 14–19 are complete locally on `feat/productization-epic`; the interactive
> Golden Path and local RC pass at unchanged migration head `a1b2c3d4e5f6`.
> The remainder of this document records historical handoff material from the
> earlier Source Asset milestone; do not use its old branch, head, or next-step
> instructions as current scope.

Generated: 2026-07-16 Asia/Hong_Kong.

This file is for handing the repository to a new ChatGPT/Codex account. It records the repository state from fresh local inspection and must be read before continuing work.

## Repository identity

- Repository name: `ai-video-preproduction-agent`
- Local path: `/Users/caiqichong/Developer/ai-video-preproduction-agent`
- Current branch: `feat/review-revision-delivery`
- Current Alembic migration head: `a1b2c3d4e5f6`
- Current head migration file: `infra/migrations/versions/a1b2c3d4e5f6_create_review_revision_delivery.py`

## Recent commits

Latest 8 commits from `git log -8 --oneline --decorate`:

```text
3e28ef2 (HEAD -> feat/source-asset-intake, origin/feat/source-asset-intake) wip: continue source asset intake milestone
06c1f13 (origin/main, origin/HEAD, main) Merge pull request #4 from Eric-Cqc/feat/structured-brief-ingestion
a68ddf4 feat: add structured brief ingestion boundary
3f55517 Merge pull request #3 from Eric-Cqc/feat/versioned-brief-foundation
46d651f feat: add versioned brief foundation
555369a Merge pull request #2 from Eric-Cqc/feat/tenant-persistence-foundation
91ceb98 feat: add tenant persistence foundation
5915510 Merge pull request #1 from Eric-Cqc/feat/engineering-skeleton
```

## Git status

At inspection immediately before this handoff file was created, `git status --short` returned no output: the worktree was clean.

After creating this handoff file, the expected status is:

```text
?? docs/development/handoffs/current-handoff.md
```

Do not commit or push unless the user explicitly asks.

## Completed phases

- Phase 1: engineering constitution, product boundary, architecture docs, ADR-001 through ADR-010, project-level `AGENTS.md`.
- Phase 2: executable engineering skeleton with Next.js Web, FastAPI API, Python Worker, contracts, CI, root Makefile, local development commands.
- Phase 3: tenant-aware PostgreSQL persistence foundation with Organization, Workspace, Membership, Project, AuditEvent, UoW, repositories, migrations and tenant isolation tests.
- Phase 4: versioned Brief foundation with immutable BriefVersion, RequirementIssue, approval rules, pointer concurrency and audit.
- Phase 5: controlled Structured Brief ingestion with PostgreSQL idempotency reservation/finalize, canonical JSON validation, Brief/Version creation, replay semantics and transaction rollback tests.
- Phase 6 Milestone A: controlled Source Asset intake governance and ADR-027 through ADR-031.
- Phase 6 Milestone B: `SourceAsset` / immutable `SourceAssetVersion` domain model, validation rules, `source_assets` / `source_asset_versions`, current pointer FK, supersedes FK and PostgreSQL constraint tests.
- Phase 6 Milestone C: tenant-scoped SourceAsset repositories, UoW integration, `source_asset_operations`, source mutation idempotency, CAS, duplicate indicator, audit and service-level tests.
- Stage 10: Brief candidate human review completed and merged into `main`.
- Stage 11: Creative Concept and Script workflow completed and merged into `main`.
- Stage 12A/B: Storyboard and Shot Plan immutable persistence, deterministic offline generation, semantic validation, services, APIs, replay, permissions, concurrency, rollback and contract tests completed on `feat/storyboard-shot-plan`.
- Stage 13: immutable planning review, revision successor lineage, deterministic delivery package and JSON/CSV/ZIP export workflow is implemented on `feat/review-revision-delivery`.

## Current stage and milestone

- Current stage: Stage 13 — Review, Revision and Delivery.
- Current milestone: implementation complete for local verification; no Stage 14 scope.
- Current plan file: `docs/development/plans/review-revision-delivery-plan.md`
- Current plan status: persistence, service/API, deterministic offline export and validation gates are implemented.

## Current stage completed content

Milestone A:

- Added ADR-027 through ADR-031.
- Froze metadata-only SourceAsset boundary.
- Froze declared SHA-256 semantics: syntactic validation only, no byte verification.
- Froze no automatic duplicate merge.

Milestone B:

- Added `services/api/app/domain/source_asset.py`.
- Added migration `c4f1d2a9b8e7_create_source_asset_metadata_boundary.py`.
- Added `source_assets` and `source_asset_versions`.
- Enforced same-aggregate current pointer and same-aggregate supersedes composite FKs.
- Added domain and PostgreSQL constraint tests.

Milestone C:

- Added `SourceAssetRepository`, `SourceAssetVersionRepository`, `SourceAssetOperationRepository` ports.
- Added SQLAlchemy implementations and UoW wiring.
- Added `source_asset_operations` via migration `d6e7f8a9b0c1_create_source_asset_operations.py`.
- Added `SourceAssetApplicationService` for non-API use cases:
  - create SourceAsset;
  - create SourceAssetVersion;
  - archive SourceAsset.
- Implemented PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING` reservation.
- Implemented strict `finalize_accepted()` condition update.
- Implemented SourceAsset aggregate CAS for pointer movement and archive.
- Added bounded duplicate-content count scoped only to same tenant and Project.
- Added audit actions:
  - `source_asset.created`;
  - `source_asset.version_created`;
  - `source_asset.archived`.

## Historical source-asset milestone status

The following statements describe the historical Source Asset handoff and are not
current Stage 12 work:

- No SourceAsset HTTP API routes.
- No SourceAsset presentation schemas.
- No SourceAsset API status-code mapping.
- No optional ordered Brief ingestion attachment request fields.
- No `BriefIngestionSourceAsset` attachment table yet.
- No attachment digest integration with Structured Brief ingestion.
- No API tests for SourceAsset endpoints or Brief ingestion attachments.

Historical Milestone E was not implemented on that branch:

- Documentation updates for final source asset API behavior.
- Final full diff review for the entire sixth milestone.
- Final CI-oriented review after Milestone D/E.

## Stage 12 completion handoff

- Immutable tables: `storyboard_runs`, `storyboard_versions`, `shot_plan_runs`,
  `shot_plan_versions`, and `visual_planning_operations`.
- Composite tenant/workspace/project lineage pins ScriptVersion and the complete
  Brief/Concept/Selection lineage; Shot Plan pins StoryboardVersion.
- Generation services resolve accepted replay before lifecycle checks, reserve
  through PostgreSQL, validate strict JSON/schema/semantics, create immutable
  artifacts, finalize by CAS, append bounded audit and commit once through UoW.
- Deterministic fixture provider is offline-only with bounded valid, malformed,
  schema, traceability, duration, continuity, safety, refusal, timeout and error
  modes. It never calls a network, SDK, tool, shell, image or video generator.
- API routes are tenant scoped, owner/admin/member mutation-only, viewer-readable,
  use Idempotency-Key, return 201/200 replay/409 digest conflict and opaque 404s,
  and do not expose request digests, keys, operation rows, prompts or raw output.
- Stage 12A and Stage 12B targeted PostgreSQL tests, migration checks, contract
  parity, `make test` and full `make check` are the required final gates.

## Stage 13 implementation handoff

- `planning_reviews` records exact human approval, rejection and revision
  requests for Script, Storyboard, Shot Plan or a complete planning bundle.
- `planning_revision_requests` and `planning_artifact_revision_links` preserve
  immutable successor lineage; predecessor rows are never updated.
- Delivery packages pin approved artifact IDs and content digests. Exports are
  deterministic JSON/CSV/README/ZIP bytes staged through StoragePort.
- All Stage 13 mutations use scoped digest idempotency, CAS finalization,
  bounded audit actions and opaque 404/role checks. The deterministic fixture
  remains offline-only; no real provider, network, renderer, job or UI exists.
- Stage 13 head is `a1b2c3d4e5f6`; the plan and ADR-058 through ADR-063 are the
  authoritative implementation references.

## Frozen architecture and security decisions

- Product is an AI video preproduction system, not an automatic video rendering, editing, publishing or ad-delivery platform.
- Architecture remains a modular monolith.
- PostgreSQL is the current persistence boundary.
- UoW is the only commit/rollback owner.
- Repositories may flush but must not commit or rollback.
- All Project, Brief and SourceAsset access is tenant + Workspace + Project scoped.
- SourceAssetVersion is immutable after insert.
- SourceAsset uses `active | archived` lifecycle only.
- SourceAsset current pointer is protected by same-aggregate composite FK and CAS.
- SourceAssetVersion `supersedes_version_id` is protected by same-aggregate composite FK.
- Source mutations use scoped PostgreSQL reservation/finalize, not a generic idempotency framework.
- Digest inputs use deterministic JSON + SHA-256, not `repr`.
- Declared checksum is metadata only and must not claim byte verification.
- Duplicate detection is tenant + Project scoped and does not merge or block creation.
- Audit payload must not contain checksum value, filename, source reference, external record ID, idempotency key, request digest, headers or secrets.
- Browser must not call model/provider APIs directly.
- External providers, storage, parsing, OCR, AI, Job/queue and cloud resources are outside current scope.

## Decisions not to reopen

Do not re-discuss or reverse these without explicit user instruction and a new ADR:

- modular monolith over microservices;
- npm workspaces without Turborepo/Nx;
- Python `.venv` and `uv.lock`;
- PostgreSQL + Alembic for persistence and migrations;
- tenant-aware foundation from day one;
- repository + UoW transaction ownership;
- immutable BriefVersion and immutable SourceAssetVersion;
- PostgreSQL partial unique indexes for Membership NULL-scope uniqueness;
- PostgreSQL reservation/finalize idempotency for ingestion/source mutations;
- no browser provider calls;
- no file upload/storage/parsing/OCR in SourceAsset metadata intake;
- SHA-256 declared digest is not byte verification.

## Dependencies and runtime versions

Runtime files:

- `.node-version`: `24.18.0`
- `.python-version`: `3.13.5`
- root package manager: `npm@11.16.0`
- Python dependency manager: `uv`, locked by `uv.lock`; CI bootstraps `uv==0.11.11`

Selected JavaScript lockfile versions:

- Next.js: `16.2.10`
- TypeScript: `5.9.3`
- Vitest: `4.1.10`
- ESLint: `9.39.5`
- Prettier: `3.9.5`
- `@rolldown/binding-linux-x64-gnu`: `1.1.5` as root optional dependency

Selected Python lockfile versions:

- Alembic: `1.18.5`
- FastAPI: `0.139.0`
- Pydantic: `2.13.4`
- pydantic-settings: `2.14.2`
- psycopg: `3.3.4`
- SQLAlchemy: `2.0.51`
- Uvicorn: `0.51.0`
- pytest: `9.1.1`
- Ruff: `0.15.21`
- mypy: `1.20.2`
- httpx: `0.28.1`

## Database and Docker commands

Local PostgreSQL uses Docker Compose and `postgres:17-alpine`.

Commands:

```bash
make db-up
make db-status
make db-upgrade
make db-current
make db-check
make db-downgrade
make db-down
```

Default database URLs from `Makefile`:

```text
DATABASE_URL=postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_local
TEST_DATABASE_URL=postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test
```

If Docker socket access is blocked by the sandbox, request explicit approval for the relevant `make db-*` command. Do not install Docker, modify Docker Desktop global configuration, or touch other projects' containers/volumes.

## Full gate commands

Use Makefile as public entry. Node/npm commands inside Makefile go through `./scripts/run-with-node.sh`.

```bash
make db-up
make db-upgrade
make db-check
make format-check
make lint
make typecheck
TEST_DATABASE_URL=postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test make test
make contract-check
make build
TEST_DATABASE_URL=postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test make check
git diff --check
```

Do not run bare `node`, `npm` or `npx` directly.

## Current test count and latest result

Latest full local gate result before this handoff:

- `make check`: passed.
- JavaScript contract tests: 2 files, 8 tests passed.
- JavaScript Web tests: 4 files, 10 tests passed.
- Python `pytest` in `make test`: 161 tests passed.
- Contract-check Python tests: 9 tests passed.
- SourceAsset targeted PostgreSQL tests: 41 tests passed.
- `make db-check`: `d6e7f8a9b0c1 (head)`, `No new upgrade operations detected.`
- `git diff --check`: no output.

## Known warnings and acceptable limits

- Warning: `StarletteDeprecationWarning` from `fastapi.testclient` / Starlette about `httpx`; accepted for now, previously deferred.
- `AGENTS.md` still says the current phase is fifth stage Structured Brief ingestion. Actual current plan is sixth stage, Milestone C complete. Update this only when explicitly asked or during Milestone E documentation cleanup.
- `FOUNDATION.md` also describes the current stage as fifth stage. Treat source asset handoff and source asset plan as newer stage-specific context.
- Ignored generated/cached directories exist locally, such as `.venv`, `node_modules`, `.next`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache` and `__pycache__`. They are ignored and not part of Git status.
- SourceAsset currently stores metadata only. It does not upload, fetch, parse, OCR, verify, store or inspect bytes.

## Current must-fix items

No current must-fix item is known.

Before starting Milestone D, verify `git status --short` only shows this handoff file if it has not been staged/committed by the user.

## Next exact execution order

1. Read this file completely.
2. Run `git status --short`.
3. Read `FOUNDATION.md`, `AGENTS.md`, and note their current-stage text is stale relative to `docs/development/plans/source-asset-intake-plan.md`.
4. Read ADR-027 through ADR-031.
5. Read:
   - `docs/development/plans/source-asset-intake-plan.md`;
   - `services/api/app/domain/source_asset.py`;
   - `services/api/app/application/source_asset_services.py`;
   - `services/api/app/application/repositories.py`;
   - `services/api/app/infrastructure/repositories.py`;
   - `services/api/app/infrastructure/models.py`;
   - `infra/migrations/versions/c4f1d2a9b8e7_create_source_asset_metadata_boundary.py`;
   - `infra/migrations/versions/d6e7f8a9b0c1_create_source_asset_operations.py`;
   - `services/api/tests/test_source_asset_services.py`;
   - `services/api/tests/test_source_asset_constraints.py`.
6. Confirm current Alembic head with `UV_CACHE_DIR=.cache/uv uv run --frozen --offline alembic heads`.
7. Continue Milestone D only:
   - add bounded SourceAsset API endpoints;
   - add API request/response schemas;
   - add optional ordered Brief ingestion attachment linkage;
   - add attachment table/migration only if needed by Milestone D requirements;
   - keep replay precedence and idempotency semantics;
   - add API and PostgreSQL tests.
8. Run relevant targeted tests first.
9. Run `make db-check`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make contract-check`, `make build`, `make check`, and `git diff --check`.
10. Do not commit or push unless the user explicitly asks.

## Out-of-scope features not allowed

Do not add:

- file upload;
- file storage;
- byte checksum verification;
- parser, PDF/DOCX/XLSX extraction or OCR;
- URL fetching or external retrieval;
- AI, LLM, prompt generation or model-provider calls;
- Kling, Seedance, OpenAI or other provider SDKs;
- Supabase, Vercel or cloud resources;
- Redis, Kafka, Celery, production queue or background Job implementation;
- new UI;
- authentication provider SDK;
- payment;
- team collaboration permissions beyond current Membership rules;
- generated SDK complexity;
- Turborepo or Nx;
- SQLite fallback or a second database driver;
- Docker as the only development path.

## Files the next account must read first

Minimum required reading:

- `docs/development/handoffs/current-handoff.md`
- `FOUNDATION.md`
- `AGENTS.md`
- `.codex/config.toml`
- `scripts/run-with-node.sh`
- `Makefile`
- `pyproject.toml`
- `package.json`
- `.github/workflows/ci.yml`
- `docs/development/plans/source-asset-intake-plan.md`
- `docs/adr/ADR-027-source-asset-aggregate-and-immutable-versions.md`
- `docs/adr/ADR-028-source-content-identity-and-duplicates.md`
- `docs/adr/ADR-029-source-metadata-and-provenance-limits.md`
- `docs/adr/ADR-030-source-asset-attachment-to-brief-ingestion.md`
- `docs/adr/ADR-031-source-lifecycle-and-audit-boundary.md`
- `services/api/app/domain/source_asset.py`
- `services/api/app/application/source_asset_services.py`
- `services/api/app/application/repositories.py`
- `services/api/app/application/uow.py`
- `services/api/app/infrastructure/models.py`
- `services/api/app/infrastructure/repositories.py`
- `services/api/app/infrastructure/uow.py`
- `infra/migrations/versions/c4f1d2a9b8e7_create_source_asset_metadata_boundary.py`
- `infra/migrations/versions/d6e7f8a9b0c1_create_source_asset_operations.py`
- `services/api/tests/domain/test_source_asset.py`
- `services/api/tests/test_source_asset_constraints.py`
- `services/api/tests/test_source_asset_services.py`
- `services/api/tests/test_migrations.py`
- `services/api/app/application/ingestion_services.py`
- `services/api/app/presentation/ingestion_routes.py`
- `services/api/app/presentation/ingestion_schemas.py`

## Startup prompt for the new ChatGPT/Codex account

```text
You are taking over the repository at /Users/caiqichong/Developer/ai-video-preproduction-agent on branch feat/source-asset-intake.

First, do not implement anything yet. Read docs/development/handoffs/current-handoff.md completely, then inspect the repository state yourself with git status --short, git branch --show-current, git log -8 --oneline --decorate, and UV_CACHE_DIR=.cache/uv uv run --frozen --offline alembic heads.

Then read FOUNDATION.md, AGENTS.md, docs/development/plans/source-asset-intake-plan.md, ADR-027 through ADR-031, the SourceAsset domain/application/infrastructure files, migrations c4f1d2a9b8e7 and d6e7f8a9b0c1, and the SourceAsset tests listed in the handoff.

Important: FOUNDATION.md and AGENTS.md still describe the current stage as fifth stage; do not rewrite history or restart from there. The actual current stage is sixth foundation milestone, Source Asset intake. Milestone A, B and C are complete. Continue with Milestone D only.

Do not redo completed Milestone A-C work. Do not reinstall dependencies, do not add new dependencies, do not commit, do not push, and do not create cloud resources. All Node/npm commands must go through ./scripts/run-with-node.sh or the Makefile. Python must use the repository .venv and uv workflow.

Milestone D scope: add bounded SourceAsset API endpoints and optional ordered Brief ingestion SourceAssetVersion attachment linkage while preserving tenant scoping, idempotency replay precedence, immutable SourceAssetVersion, no upload/storage/parsing/OCR/AI/provider/job/UI, safe audit payloads, and PostgreSQL-backed constraints. Start by producing a short execution plan from the current repository state, then implement and validate with targeted tests before full make check.
```
