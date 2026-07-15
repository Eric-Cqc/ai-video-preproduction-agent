# AI Video Preproduction Agent

This repository contains the executable foundation for an **AI video preproduction system**. The current milestone establishes tenant-aware PostgreSQL persistence and a minimal Project container; it does not generate, edit, render, publish, or deliver video.

## Current capabilities

- Next.js foundation status page and canonical cross-language health contract.
- FastAPI health plus minimal Organization, Workspace, Membership, Project, lifecycle, and Project audit endpoints.
- PostgreSQL 17 schema managed by Alembic, with composite tenant constraints and partial membership indexes.
- Tenant-scoped repositories, one application Unit of Work, atomic mutation/audit writes, and Project optimistic concurrency.
- Temporary local/test/ci request-context headers, explicitly not authentication.
- Python Worker one-shot readiness boundary and minimal Provider registry with no real Provider.
- Deterministic domain, PostgreSQL, isolation, transaction, API, contract, and component tests.

There is no Brief processing, upload, AI/LLM/model call, Prompt compilation, media generation, authentication Provider, production queue, billing, product UI, cloud deployment, or customer collaboration feature.

## Repository layout

```text
apps/web/                         Next.js foundation status
services/api/app/domain/         Project lifecycle and domain records
services/api/app/application/    tenant use cases, repository ports, UoW port
services/api/app/infrastructure/ SQLAlchemy/PostgreSQL adapters
services/api/app/presentation/   request context, schemas, routes, error boundary
services/worker/                  one-shot Worker readiness process
packages/contracts/               canonical health schema and validators
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

Protected resources use opaque 404 behavior. A Project ID alone is never sufficient; path, headers, Organization, Workspace, and active Membership must all agree.

## Minimal API surface

- `POST/GET /api/v1/organizations...`
- `POST/GET /api/v1/organizations/{organization_id}/workspaces...`
- `POST .../memberships`
- `POST/GET/PATCH .../projects...`
- `POST .../projects/{project_id}/activate`
- `POST .../projects/{project_id}/archive`
- `GET .../projects/{project_id}/audit-events`

Project PATCH only accepts `name`, `description`, and `expected_version`. Status changes use explicit lifecycle endpoints. Stale versions, invalid lifecycle changes, and slug conflicts return 409. Errors use `{error: {code, message, correlation_id}}` and never expose raw SQL or stack traces.

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
| `DATABASE_URL`                  | repository-local PostgreSQL URL | Application/migration database              |
| `TEST_DATABASE_URL`             | `foundation_test` URL           | Isolated persistence-test database          |
| `DATABASE_POOL_SIZE`            | `5`                             | SQLAlchemy pool size                        |
| `DATABASE_MAX_OVERFLOW`         | `5`                             | Pool overflow limit                         |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `10`                            | Pool checkout timeout                       |
| `DATABASE_ECHO`                 | `false`                         | Local/test SQL diagnostics only             |
| `WEB_HOST` / `WEB_PORT`         | `127.0.0.1` / `3000`            | Web bind address                            |
| `WORKER_LOG_LEVEL`              | `INFO`                          | Worker structured log level                 |

The checked-in values are local test credentials only. Production requires an explicit database URL; credentials are redacted from application diagnostics and must never be committed or logged.

## Architecture and milestone status

The authoritative constraints are [FOUNDATION.md](FOUNDATION.md), [AGENTS.md](AGENTS.md), the [architecture documents](docs/architecture/), and [ADRs](docs/adr/). ADR-012 through ADR-016 record the replaceable persistence implementation. The execution record is [tenant-persistence-foundation-plan.md](docs/development/plans/tenant-persistence-foundation-plan.md).

The next intended milestone is a versioned Brief contract and domain foundation. It must preserve tenant, audit, and structured-schema rules and must not add AI generation unless separately approved.
