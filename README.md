# AI Video Preproduction Agent

This repository contains the executable foundation for an **AI video preproduction system**. The current milestone adds controlled ingestion of already structured Brief JSON; it does not upload or parse files, fetch URLs, use AI, generate prompts, render, publish, or deliver video.

## Current capabilities

- Next.js foundation status page and canonical cross-language health contract.
- FastAPI health plus Organization, Workspace, Membership, Project and versioned Brief foundation endpoints.
- PostgreSQL 17 schema managed by Alembic, with composite tenant constraints and partial membership indexes.
- Tenant-scoped repositories, one application Unit of Work, atomic mutation/audit writes, and Project optimistic concurrency.
- Canonical Structured Brief v1 JSON Schema, immutable BriefVersion snapshots, deterministic requirement issues, explicit review/approval, and Brief optimistic concurrency.
- Project-scoped structured ingestion with canonical validation, stable serialization/SHA-256 digest, PostgreSQL idempotency, replay and atomic audit.
- Temporary local/test/ci request-context headers, explicitly not authentication.
- Python Worker one-shot readiness boundary and minimal Provider registry with no real Provider.
- Deterministic domain, PostgreSQL, isolation, transaction, API, contract, and component tests.

There is no file upload or parsing, AI/LLM/model call, Prompt compilation, media generation, authentication Provider, production queue, billing, product UI, cloud deployment, or customer collaboration feature.

## Controlled structured ingestion

The API supports `create_brief` and `create_version` only for pre-structured canonical Brief JSON. Each mutation requires an 8–128-character printable ASCII `Idempotency-Key`, scoped to Organization, Workspace, Project and operation. The server validates the canonical schema, deterministically serializes result-affecting input, and computes SHA-256. A matching accepted request replays with 200 and no new audit; a different digest returns 409. `reserved` exists only within the winning database transaction and is never returned.

`source_reference` is a bounded opaque identifier, not a path, URL, database URL, credential or Authorization-like value. HTTP bodies remain capped at 256 KiB and canonical content at 128 KiB. PostgreSQL statement timeout defaults to 5000ms, bounding stalled unique-key waits; timeout rollback leaves no reservation.

## Repository layout

```text
apps/web/                         Next.js foundation status
services/api/app/domain/         Project and versioned Brief domain rules
services/api/app/application/    tenant use cases, repository ports, UoW port
services/api/app/infrastructure/ SQLAlchemy/PostgreSQL adapters
services/api/app/presentation/   request context, schemas, routes, error boundary
services/worker/                  one-shot Worker readiness process
packages/contracts/               canonical health and Structured Brief schemas
packages/model-registry/          minimal future Adapter boundary
infra/migrations/                 Alembic migration history
infra/docker/                     optional local PostgreSQL 17 only
tests/integration/                cross-component contract tests
docs/                             product, architecture, ADR, and development rules
```

## Prerequisites

- Node.js 24.18.0 with npm 11; local Node selection uses `fnm` when available.
- Python 3.13.5 and uv 0.11.11 or a compatible uv release.
- GNU Make and Bash.
- PostgreSQL 17, either installed natively or supplied by the optional Docker path.

Docker is not required when a native PostgreSQL instance is available. No cloud account, external Provider credential, or production credential is required.

## Setup

```sh
make setup
cp .env.example .env
```

`make setup` installs locked npm dependencies from the official npm registry and Python dependencies into repository-local `.venv` from official PyPI. It does not start PostgreSQL.

For the optional repository-scoped Docker database:

```sh
make db-up
make db-upgrade
make db-status
```

For native PostgreSQL, create separate `foundation_local` and `foundation_test` databases, set `DATABASE_URL` and `TEST_DATABASE_URL`, then run `make db-upgrade`. Both URLs must use `postgresql+psycopg`; there is no SQLite fallback.

## Database commands

```sh
make db-up          # optional Docker PostgreSQL only
make db-down        # stops this Compose project; preserves its named volume
make db-upgrade
make db-current
make db-check
make db-downgrade   # explicit one-revision downgrade
make db-reset-test  # truncates only a database whose name ends in _test
```

Create a migration after changing SQLAlchemy metadata:

```sh
DATABASE_URL="$DATABASE_URL" PYTHONPATH=.:packages/contracts/python:packages/model-registry \
  UV_CACHE_DIR=.cache/uv uv run --frozen --offline alembic revision --autogenerate -m "describe change"
make db-check
```

Review every generated constraint, index, upgrade, and downgrade. Never reset or truncate a non-test database through repository helpers.

## Local development

```sh
make dev-api
make dev-web
make dev-worker
```

Run API and Web in separate terminals, then open `http://127.0.0.1:3000`. The Worker remains a one-shot readiness check with zero production handlers.

## Temporary actor and tenant context

Persistence routes require development-only context headers:

- `X-Actor-Subject`
- `X-Organization-Id` for Organization-scoped routes
- `X-Workspace-Id` for Workspace/Project routes
- optional `X-Correlation-Id`

Organization bootstrap requires only `X-Actor-Subject`; it atomically creates the Organization and initial owner Membership. The headers are accepted only when `APP_ENVIRONMENT` is `local`, `test`, or `ci`. They are spoofable context injection, **not authentication**, and are rejected in every other environment.

Protected resources use opaque 404 behavior. A Project/Brief/Version ID alone is never sufficient; path, headers, Organization, Workspace, parent ownership and active Membership must all agree.

## Minimal API surface

- `POST/GET /api/v1/organizations...`
- `POST/GET /api/v1/organizations/{organization_id}/workspaces...`
- `POST .../memberships`
- `POST/GET/PATCH .../projects...`
- `POST .../projects/{project_id}/activate`
- `POST .../projects/{project_id}/archive`
- `GET .../projects/{project_id}/audit-events`
- `POST/GET .../projects/{project_id}/briefs`
- `GET .../briefs/{brief_id}` and `POST/GET .../versions`
- explicit `submit`, `approve`, `archive`, issue create/resolve/dismiss, and Brief audit reads

Project PATCH only accepts `name`, `description`, and `expected_version`. Status changes use explicit lifecycle endpoints. Stale versions, invalid lifecycle changes, and slug conflicts return 409. Errors use `{error: {code, message, correlation_id}}` and never expose raw SQL or stack traces.

Brief content is accepted only as canonical Structured Brief v1 and is never PATCHed in place. Every content change creates a complete immutable snapshot and atomically advances the aggregate pointer using the expected Brief version and expected current-version ID. Members may draft, version, submit and manage issues; only owner/admin may approve or archive; viewers are read-only. Open blocking issues prevent approval.

## Validation

```sh
make format
make lint
make typecheck
make test-domain
make test-persistence
make test-integration
make contract-check
make build
make check
```

`make check` requires a migrated PostgreSQL database selected by `DATABASE_URL`; persistence tests use `TEST_DATABASE_URL`. It runs migration head/drift validation, formatting, lint, strict types, all tests, contract validation, and the production Web build. JavaScript commands are routed through `scripts/run-with-node.sh`.

Use `make` as the public developer entry point; do not run bare `node`, `npm`, or `npx`. A direct `npm run ...` cannot change the Node binary already used by that parent process and is unsupported.

## Environment variables

| Variable                        | Safe local default              | Purpose                                     |
| ------------------------------- | ------------------------------- | ------------------------------------------- |
| `APP_ENVIRONMENT`               | `local`                         | Environment label and temporary-header gate |
| `API_BASE_URL`                  | `http://127.0.0.1:8000`         | Server-side Web→API address                 |
| `API_HOST` / `API_PORT`         | `127.0.0.1` / `8000`            | API bind address                            |
| `API_ALLOWED_CORS_ORIGINS`      | `http://localhost:3000`         | Explicit origins; wildcard rejected         |
| `API_LOG_LEVEL`                 | `INFO`                          | Structured API log level                    |
| `API_MAX_REQUEST_BYTES`         | `262144`                        | API Content-Length guard                    |
| `DATABASE_URL`                  | repository-local PostgreSQL URL | Application/migration database              |
| `TEST_DATABASE_URL`             | `foundation_test` URL           | Isolated persistence-test database          |
| `DATABASE_POOL_SIZE`            | `5`                             | SQLAlchemy pool size                        |
| `DATABASE_MAX_OVERFLOW`         | `5`                             | Pool overflow limit                         |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `10`                            | Pool checkout timeout                       |
| `DATABASE_STATEMENT_TIMEOUT_MS` | `5000`                          | PostgreSQL statement/wait bound             |
| `DATABASE_ECHO`                 | `false`                         | Local/test SQL diagnostics only             |
| `WEB_HOST` / `WEB_PORT`         | `127.0.0.1` / `3000`            | Web bind address                            |
| `WORKER_LOG_LEVEL`              | `INFO`                          | Worker structured log level                 |

The checked-in values are local test credentials only. Production requires an explicit database URL; credentials are redacted from application diagnostics and must never be committed or logged.

## Architecture and milestone status

The authoritative constraints are [FOUNDATION.md](FOUNDATION.md), [AGENTS.md](AGENTS.md), the [architecture documents](docs/architecture/), and [ADRs](docs/adr/). ADR-012 through ADR-016 record the replaceable persistence implementation; ADR-017 through ADR-021 record the versioned Brief foundation; ADR-022 through ADR-026 record controlled structured ingestion. The execution records are [versioned-brief-foundation-plan.md](docs/development/plans/versioned-brief-foundation-plan.md) and [structured-brief-ingestion-plan.md](docs/development/plans/structured-brief-ingestion-plan.md).

The next intended milestone is a separately reviewed authorization and operational-hardening decision for this synchronous structured ingress. It must preserve tenant, immutable-version, audit, size, provenance and canonical-schema rules; file parsing, uploads, URL retrieval, OCR, AI or background processing require their own reviewed scope and ADR.
