# Hosted MVP deployment runbook

## Scope and prerequisites

This runbook operates the private, single-tenant pilot defined by
[ADR-066](../adr/ADR-066-single-tenant-hosted-mvp-boundary.md). It is not a public multi-user
deployment or production-grade identity system. Use a Linux host with Docker Engine and Docker
Compose v2, a DNS name pointing to the host, inbound TCP 80/443, persistent disk space for
PostgreSQL and application files, and an operator who can protect host environment files.

Install Docker using the vendor's supported package for the target operating system, then verify
`docker --version` and `docker compose version`. Do not install application dependencies directly
on the host.

## Configuration

Copy `.env.hosted.example` to `.env.hosted`; it is ignored by Git. Replace every placeholder.
Required values include `PILOT_DOMAIN`, PostgreSQL credentials, `PILOT_ACCESS_PASSWORD`, a
32-character-or-longer `PILOT_SESSION_SECRET`, fixed Organization/Workspace UUIDs, and the
server-only `DEEPSEEK_API_KEY` when `MODEL_PROVIDER=deepseek`. Use `MODEL_PROVIDER=deterministic_offline`
for a no-network acceptance run.

`DEEPSEEK_BASE_URL` must remain the approved HTTPS origin and `DEEPSEEK_MODEL` must remain
`deepseek-v4-flash`. Do not put either the DeepSeek key or pilot password into browser variables,
source files, shell history, tickets, or logs.

## Commands

Run these commands from the repository root:

```text
make hosted-build
make hosted-up
make hosted-bootstrap
make hosted-smoke
make hosted-logs
make hosted-down
```

`hosted-bootstrap` is transactional and idempotent. It creates the configured pilot Organization,
Workspace, and owner actor only if absent, and fails on a conflicting persisted configuration.
`hosted-smoke` deliberately does not call DeepSeek. A real Provider smoke remains a separately
authorized, key-gated action outside CI.

## Restart, rollback, and backups

Use `make hosted-down`, then `make hosted-up` to restart without deleting named volumes. Confirm
health and run `make hosted-bootstrap` again; it must report the same bounded Organization and
Workspace IDs. To roll back application code, stop the stack, check out the prior reviewed commit,
rebuild, and start it only after confirming migration compatibility. Do not roll back a database
without a tested backup and explicit migration review.

Back up the PostgreSQL named volume and `application_files` named volume together, with an
encrypted, access-controlled destination. Regularly restore into an isolated host and verify that
the project lineage and export files are both present. Rotate the pilot password and DeepSeek key
by updating `.env.hosted`, restarting the stack, and invalidating the old secret at its issuer.

## Logs and recovery

Use `make hosted-logs` for service status. Logs must not contain Provider keys, pilot credentials,
prompts, raw Provider responses, authorization headers, or customer source bodies. If Caddy cannot
obtain a certificate, validate DNS, 80/443 reachability, and the configured domain; do not expose
PostgreSQL or FastAPI directly as a workaround.
