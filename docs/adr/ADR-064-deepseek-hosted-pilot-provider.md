# ADR-064: DeepSeek hosted-pilot provider boundary

## Decision

Hosted Pilot Phase 1 permits only the server-side `deepseek-v4-flash` adapter at the exact
`https://api.deepseek.com/chat/completions` endpoint. The deterministic provider remains the
default and the only CI/test provider. Browser code never receives a key or calls a Provider.

The adapter sends bounded, server-owned JSON-only prompts with untrusted lineage content delimited
as data. It disables tools, browsing, URL/file access, redirects, proxy inheritance and arbitrary
client-selected model/base URL/request fields. Outputs remain untrusted and must pass the existing
schema and semantic validation before immutable persistence; failure creates no accepted artifact.

No full prompt, raw request/response, reasoning, secret, or customer source body is persisted,
logged, audited, or returned. Only bounded numeric usage metadata may be retained when a future
existing attempt/run field can represent it without a speculative migration. Existing lineage,
idempotency, CAS and UoW behavior remain authoritative.

## Limits and review triggers

This is an opt-in local pilot, not deployment, identity, cloud storage, queue, image/video, or
media-rendering authorization. Privacy, retention, cost, rate limit, availability and failure
behavior require human review before any hosted deployment. Live smoke is explicit, key-gated and
never part of CI or `make check`.
