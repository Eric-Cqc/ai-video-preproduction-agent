# Hosted single-tenant MVP

This is a private pilot for the AI video preproduction workflow: project → upload → Brief →
Concepts → Script → Storyboard → Shot Plan → review/revision → Delivery Package → ZIP. It is not
public multi-user production and does not generate or render media.

## Configuration and deployment

Copy `.env.hosted.example` to the ignored `.env.hosted` and replace every placeholder. The exact
Provider settings are `MODEL_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`,
`DEEPSEEK_MODEL`, `DEEPSEEK_TIMEOUT_SECONDS`, `DEEPSEEK_MAX_ATTEMPTS`,
`DEEPSEEK_MAX_INPUT_BYTES`, and `DEEPSEEK_MAX_OUTPUT_BYTES`. The fixed model is
`deepseek-v4-flash`; its key is server-only and must never be placed in browser configuration.

Configure `PILOT_DOMAIN` with a DNS name pointing to the host. Caddy terminates HTTPS and is the
only public container. PostgreSQL and the FastAPI service remain on an internal network. The
password gate uses `PILOT_ACCESS_PASSWORD` and a signed HTTP-only cookie using
`PILOT_SESSION_SECRET`; it is a private-pilot gate, not production authentication.
Only the API container receives the complete host environment file. The Web container receives
an explicit non-secret runtime allowlist and must not contain the Provider key, pilot password,
session secret, or PostgreSQL credentials.
The API alone also joins a dedicated outbound network for the approved DeepSeek HTTPS endpoint;
this does not publish an API port. PostgreSQL and Web stay on the internal network, and Caddy
remains the only public ingress service.

Run `make hosted-build`, `make hosted-up`, and `make hosted-bootstrap`. The bootstrap is
idempotent: it creates only the configured Organization, Workspace and owner actor, and rejects
conflicting persisted configuration. `make hosted-smoke` verifies internal API health without a
real Provider call. `make hosted-logs` follows bounded service logs and `make hosted-down` stops
the stack without deleting persistent volumes.

## Operations

Back up the PostgreSQL named volume and the `application_files` named volume together. Rotate the
pilot password or DeepSeek key by changing the host-only `.env.hosted` file and restarting the
stack. Never copy either value into an issue, browser setting, log, or repository. A separately
authorized live DeepSeek smoke requires `ALLOW_PROVIDER_LIVE_SMOKE=1`; it is excluded from CI and
ordinary hosted smoke.

## Limits

Deterministic offline mode remains the CI default. DeepSeek responses remain untrusted and pass
the existing JSON schema and semantic validation before immutable persistence. The pilot has no
Clerk/JWT, organization switcher, multi-tenant onboarding, Neon, R2, Vercel, Tauri, cloud object
storage, billing, media generation, or rendering. Those topics require a future decision record.
