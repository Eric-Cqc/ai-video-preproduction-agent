# ADR-066: Single-tenant hosted MVP boundary

## Decision

Hosted MVP Phase 1 authorizes one private, single-tenant deployment of the existing modular
monolith. It uses the approved server-side DeepSeek `deepseek-v4-flash` Adapter, a single
configured internal Organization and Workspace, and a password-based pilot access gate. The gate
sets only a secure HTTP-only session cookie; it is not user authentication, does not provision
tenants, and must not be represented as production-grade identity.

The browser calls the application only through the same configured HTTPS origin. Provider keys,
pilot credentials, raw provider responses, prompts, Authorization headers, and source bodies do
not enter browser code, logs, audit payloads, or persistence. Existing structured schema,
semantic validation, immutable lineage, idempotency, reviews, revisions, and exports remain
authoritative.

The deployment is a local Docker Compose stack with reverse proxy, Web, API, PostgreSQL and
persistent local upload/export volumes. PostgreSQL and API are internal-only; the proxy is the
sole public service. Deterministic mode remains the default for CI and all ordinary tests.

## Limits and review triggers

This authorizes neither Clerk/JWT nor multi-user onboarding, cloud hosting, cloud object storage,
billing, image/video generation, media rendering, queues, or a second Provider. A public or
multi-user rollout requires a new ADR covering identity, tenant isolation, privacy, retention,
availability, abuse controls, observability and incident response.
