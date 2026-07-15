# AI Video Preproduction Agent

This repository contains the executable engineering foundation for an **AI video preproduction system**. The current milestone proves component boundaries and health only; it does not generate, edit, render, publish, or deliver video.

## Current capabilities

- Next.js foundation status page with loading, connected, invalid-response, and unavailable states.
- FastAPI `GET /api/v1/health` endpoint with validated configuration, safe errors, CORS policy, and structured logs.
- Python Worker one-shot self-check reporting zero registered production job handlers.
- One canonical JSON Schema validated by both Python and TypeScript.
- Minimal Provider capability/registry boundary with no real Provider implementation.
- Deterministic tests, root quality commands, locked dependencies, and secret-free CI.

There is no authentication, database, Supabase, product CRUD, Brief processing, Prompt compilation, LLM/model call, media generation, production queue, cloud deployment, payment, or collaboration feature.

## Repository layout

```text
apps/web/                   Next.js foundation status
services/api/               FastAPI core API
services/worker/            one-shot Worker readiness process
packages/contracts/         canonical schema and language validators
packages/model-registry/    minimal future Adapter boundary
packages/test-fixtures/     deterministic foundation fixtures
infra/                      documented future infrastructure boundaries
tests/integration/          cross-component contract tests
tests/end-to-end/           deferred browser-test boundary
docs/                       product, architecture, ADR, and development rules
```

## Prerequisites

- Node.js 24.18.0 with npm 11; local Node selection uses `fnm` when available.
- Python 3.13.5.
- uv 0.11.11 or a compatible uv release.
- `make` and a POSIX-like shell.

Docker, cloud credentials, external Provider credentials, and a database are not required.

## Setup

```sh
make setup
cp .env.example .env
```

`make setup` installs npm dependencies from the official npm registry and Python dependencies into repository-local `.venv` from official PyPI. Lockfiles are authoritative. `.env` is ignored by Git and loaded by the Makefile; Python services themselves read process environment only through `pydantic-settings`.

## Local development

```sh
make dev-api
make dev-web
make dev-worker
```

Run API and Web in separate terminals, then open `http://127.0.0.1:3000`. `make dev-worker` performs a one-shot readiness check and exits. `make dev` starts the Web and API together and runs the Worker self-check; stop it with Ctrl-C.

## Validation

```sh
make format
make lint
make typecheck
make test
make contract-check
make build
make check
```

`make check` is the complete local and CI gate: formatting, JavaScript/Python lint, strict type checks, tests, explicit contract validation, and production Web build. All JavaScript commands are routed through `scripts/run-with-node.sh`.

Use `make` as the public developer entry point; do not run bare `node`, `npm`, or `npx`. Root package scripts route every subsequent npm child process through the wrapper. A direct `npm run ...` cannot technically change the Node binary already used by that parent npm process, so it is intentionally unsupported.

## Environment variables

| Variable                   | Safe local default      | Purpose                                                |
| -------------------------- | ----------------------- | ------------------------------------------------------ |
| `APP_ENVIRONMENT`          | `local`                 | Environment label emitted by every component           |
| `API_BASE_URL`             | `http://127.0.0.1:8000` | Server-side Web→API address; credentials are rejected  |
| `API_HOST` / `API_PORT`    | `127.0.0.1` / `8000`    | API bind address                                       |
| `API_ALLOWED_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated explicit origins; wildcard is rejected |
| `API_LOG_LEVEL`            | `INFO`                  | API structured log level                               |
| `WEB_HOST` / `WEB_PORT`    | `127.0.0.1` / `3000`    | Web bind address                                       |
| `WORKER_LOG_LEVEL`         | `INFO`                  | Worker structured log level                            |

No environment variable in this milestone is a cloud account identifier or secret. Never commit real secrets to `.env.example` or logs.

## Architecture and milestone status

The authoritative constraints are [FOUNDATION.md](FOUNDATION.md), [AGENTS.md](AGENTS.md), the [architecture documents](docs/architecture/), and [ADRs](docs/adr/). [ADR-011](docs/adr/ADR-011-engineering-skeleton-toolchain.md) records this replaceable toolchain implementation. The detailed execution record is [engineering-skeleton-plan.md](docs/development/plans/engineering-skeleton-plan.md).

The next intended milestone is a domain-schema foundation: define the first tenant-aware, versioned preproduction project/Brief contracts and persistence decision without adding AI generation or automatic video production.
