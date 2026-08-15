# Hosted Pilot Operations Runbook

Status: Verified against the actual Stage 21 Makefile/scripts on a real host, 2026-08-15.

This runbook operates the private, single-tenant hosted pilot defined by
[ADR-066](../adr/ADR-066-single-tenant-hosted-mvp-boundary.md) and the server-side Provider
boundary defined by [ADR-064](../adr/ADR-064-deepseek-hosted-pilot-provider.md), with the
Stage 21 hardening recorded in [ADR-067](../adr/ADR-067-hosted-pilot-review-outcome.md) and
[HOSTED_PILOT_REVIEW.md](HOSTED_PILOT_REVIEW.md).

It is not a public, multi-tenant, production identity, automatic video-generation, media-
rendering, publishing, or cloud-storage system.

All commands run from the repository root. `HOSTED_COMPOSE` (used internally by the Makefile) is:

```text
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml
```

## Frozen decisions

Unchanged: modular monolith, single-tenant private pilot, PostgreSQL/API internal-only, Caddy the
only public container, local filesystem storage, deterministic mode as default/kill-switch, no
new monitoring stack, no queue/scheduler.

## 1. Prerequisites and environment file

Prerequisites: Docker Engine + Compose v2, GNU Make, `curl`, `lsof` (used by RC/Makefile process
ownership checks — a fallback exists if absent, with a logged warning), a reviewed checkout.

### Local validation (no real key, no DNS/TLS needed)

```sh
make hosted-env-local
```

This generates `.env.hosted` with `PILOT_DOMAIN=localhost`, `MODEL_PROVIDER=deterministic_offline`,
and strong random secrets. It refuses to overwrite an existing file. This is the path verified
end-to-end on a real host in Stage 21: `hosted-build → hosted-up → hosted-bootstrap →
hosted-smoke → hosted-backup → hosted-down`, all exited 0 with four healthy containers and a
passing proxy smoke.

### Production-shaped deployment

```sh
cp .env.hosted.example .env.hosted
```

Replace every placeholder. Never print, commit, or back up `.env.hosted` itself. Required values
are documented in `.env.hosted.example`; `PILOT_SESSION_SECRET` must be at least 32 characters.

Verify only service/volume names (avoid unrestricted `config` output, which can print
interpolated secrets):

```sh
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml config --services
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml config --volumes
```

Expected services: `postgres api web caddy`. Expected volumes: `postgres_data application_files
caddy_data caddy_config`.

## 2. Topology and persistent data

| Service | Role | Persistence / exposure |
| --- | --- | --- |
| `postgres` | PostgreSQL 17 | Internal network; `postgres_data` |
| `api` | FastAPI modular monolith | Internal network; `application_files` at `/var/lib/ai-video-preproduction`; healthcheck |
| `web` | Production Web container | Internal network; **now receives only non-secret vars, not the full `.env.hosted`** (Stage 21 V1); healthcheck |
| `caddy` | HTTPS reverse proxy | Public 80/443; `caddy_data`, `caddy_config`; healthcheck; forwards `X-Forwarded-For` |

`application_files/source-objects/` contains `staging/` (in-progress uploads) and `objects/`
(finalized source uploads and delivery export files). There are no separate upload/export
volumes.

## 3. Start, stop, status

```sh
make hosted-build
make hosted-up
make hosted-bootstrap
make hosted-smoke
```

`hosted-up` waits for all four services to report healthy (Web and Caddy healthchecks were added
in Stage 21; previously only PostgreSQL/API had them). `hosted-bootstrap` runs migrations then the
idempotent bootstrap script inside the `api` container. `hosted-smoke` now runs
`infra/scripts/hosted_proxy_smoke.py` **inside the API container against the Caddy proxy origin**
(`http://caddy:80` on the internal network, with Host-header/SNI handling for the configured
domain) — it exercises unauthenticated 401, wrong-password rejection, real login with cookie-flag
assertions, the full deterministic Golden Path workflow (upload → ... → ZIP with checksum
verification), replay/409, cross-tenant 404, viewer-membership persistence, logout, and a real
bootstrap-idempotency assertion (the bootstrap script runs twice and the owner membership is
checked for unchanged ID, actor, role, and active status). It does not claim viewer-role mutation
denial: the hosted pilot cookie always authenticates the one configured pilot actor, so no genuine
viewer session can be issued by this access model. Viewer RBAC denial remains covered by the
application/API tests. This replaced the old internal-health-only check.

Status:

```sh
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml ps
```

Stop (retains volumes):

```sh
make hosted-down
```

Never add `--volumes` unless you intentionally want to destroy hosted data and have a verified
backup.

## 4. Backup

```sh
BACKUP_DIR=/secure/backups/ai-video-preproduction make hosted-backup
```

This is a real, live-verified target (Stage 21 R5): it refuses to run without `.env.hosted` and
without `BACKUP_DIR`; it stops `caddy`, `web`, `api` (quiescing writers), takes a `pg_dump
--format=custom` via `compose exec -T postgres` (password read from the service environment, not
the CLI), archives the `application_files` volume via a temporary `api` container, writes a
sha256 manifest, and restarts the full stack via a trap that fires on success, failure, or
interrupt. Verified output on a real host: a `postgres-<stamp>.dump`, an
`application-files-<stamp>.tar`, and a `manifest-<stamp>.sha256` in `BACKUP_DIR`, with the stack
returning to healthy afterward.

There is still no backup schedule, retention policy, or automated restore test — those remain
operator responsibilities.

## 5. Restore

Restore is a manual, documented procedure (not yet a Make target):

1. Verify the backup files exist and the manifest checksums match.
2. `make hosted-down` (retains volumes; this only stops containers).
3. Start only `postgres`: `docker compose ... up --detach --wait postgres`.
4. Restore the dump: `docker compose ... exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD"
   pg_restore --clean --if-exists --no-owner --username="$POSTGRES_USER"
   --dbname="$POSTGRES_DB"' < postgres-<stamp>.dump`.
5. Restore `application_files` from the tar archive via a temporary `api` container (clear the
   mount first, then extract).
6. Start `postgres api`, run `alembic current --check-heads` and `hosted_bootstrap` to verify.
7. Only then start `web caddy` and run `make hosted-smoke`.
8. Manually verify a known restored project and delivery ZIP through the UI.

This procedure has not itself been live-tested end to end in Stage 21 (backup was verified;
restore was not exercised against real data). Test it before relying on it operationally.

## 6. Upgrade

```sh
git pull --ff-only
make check
make hosted-build
make hosted-down
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml up --detach --wait postgres api
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml exec -T api alembic upgrade head
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml exec -T api python -m infra.scripts.hosted_bootstrap
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml up --detach --wait web caddy
make hosted-smoke
```

Take a backup before any schema-changing release. There is no hosted-specific migration rollback
guard; prefer restoring from backup over a live `alembic downgrade` against production data.

## 7. Logs

```sh
make hosted-logs
```

Follows all four services' last 100 lines. No hosted log aggregation, rotation, or retention
policy exists (out of Stage 21 scope — no new monitoring stack). The following must never appear
in logs, tickets, or incident messages: `DEEPSEEK_API_KEY`, `POSTGRES_PASSWORD`,
`PILOT_ACCESS_PASSWORD`, `PILOT_SESSION_SECRET`, signed pilot cookies, prompts, raw provider
responses, or source text.

## 8. Incident quick actions

**Take the pilot offline:** `docker compose ... stop caddy` (do not expose Postgres/API directly
as a workaround).

**Deterministic fallback (kill-switch):** set `MODEL_PROVIDER=deterministic_offline` in
`.env.hosted`, then `make hosted-down && make hosted-up`.

**Rotate the DeepSeek key:** flip to deterministic mode first, revoke the old key at DeepSeek,
update `DEEPSEEK_API_KEY` in `.env.hosted`, restore `MODEL_PROVIDER=deepseek`, restart.

**Rotate the pilot password/session secret:** update `PILOT_ACCESS_PASSWORD` (and
`PILOT_SESSION_SECRET` to invalidate existing cookies immediately) in `.env.hosted`, restart.

**Pilot gate rate limiting (Stage 21 V4 change):** in hosted mode, the failed-login limiter now
keys on the first `X-Forwarded-For` hop set by Caddy, not the shared proxy address — a bad actor
can no longer lock out every pilot user by tripping the limiter from behind the same proxy. This
does not change the rotation procedure above.

## 9. Manual health and disk monitoring

```sh
docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml ps
make hosted-smoke
docker system df -v
df -h
```

Do not run `docker system prune` or delete named volumes as a disk-space response.
