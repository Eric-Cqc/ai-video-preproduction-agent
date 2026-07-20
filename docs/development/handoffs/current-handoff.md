# Current project handoff

Generated: 2026-07-21 Asia/Hong_Kong.

## Resume objective

Resume Tencent Cloud production acceptance from the bounded DeepSeek Provider fix. Do not
redeploy the whole stack, run migrations, change PostgreSQL/Caddy, expose credentials, or restart
productization planning. The next action is to deploy the already-tested API commit described
below, then continue the existing Golden Path.

## Repository and production state

- Repository: `/Users/caiqichong/Developer/ai-video-preproduction-agent`
- Branch: `feat/hosted-single-tenant-mvp`
- Validated Provider implementation commit: `df18ce04ee37bfc2c1bdd48490a2ffce821473c7`.
  The current branch tip also contains this handoff; confirm `df18ce0` is its ancestor rather than
  resetting the branch tip to the implementation commit.
- Production repository: `/home/ubuntu/ai-video-preproduction-agent`
- Production HEAD: `5ef10df72cdb893f38dabae748dbb3fe9ff4d189`
- Migration head: `a1b2c3d4e5f6`; no migration is required by the pending commit
- Local working tree after this handoff commit: expected clean
- Production working tree: clean when last checked
- Domain: `app.gemaogejiaojiao.cn`
- API health: HTTPS 200
- Web: HTTPS 200
- Containers: API healthy, PostgreSQL healthy, Web running, Caddy running

Relevant commits:

1. `fa467e4 fix: restore hosted pilot access`
2. `1273c38 fix: keep hosted secrets out of web`
3. `5ef10df fix: allow hosted provider egress`
4. `df18ce0 fix: bound DeepSeek structured output` — tested locally, not yet deployed

## Security state

- The previously exposed pilot password and session-signing secret were rotated successfully.
- Do not inspect, print, copy or report `.env.hosted`, container environment values, cookies,
  tokens, Provider keys, Prompts, raw responses or reasoning content.
- Web now receives only an explicit non-secret runtime allowlist. Production verification printed
  `WEB_SECRET_ISOLATION=pass`.
- API alone joins `internal` and `provider_egress`; it publishes no host port. PostgreSQL and Web
  remain internal-only, and Caddy remains the only public ingress service.
- A temporary acceptance SSH key is installed for `ubuntu` with comment
  `codex-video-agent-acceptance-2026-07-21`. Its local private key is
  `/tmp/codex-video-agent-deploy-key`. Remove the matching public-key line from the server and
  delete both local key files only after final acceptance. If the local key is unavailable in a
  future runtime, use the existing Tencent OrcaTerm TAT session rather than requesting secrets.

## Acceptance evidence so far

- Production login with the rotated credential: passed.
- Refresh after login retained the session: passed.
- Protected project creation proved hosted tenant identity propagation: passed.
- Test project: `Hosted Pilot Acceptance 2026-07-20`; it contains only synthetic fixture data.
- Project → SourceAsset → upload → parse → Brief extraction run all returned 201.
- Candidate read returned opaque 404 because the recorded attempt was
  `provider_error`, with zero output characters.
- Root cause of the first Provider failure: API was attached only to a Docker
  `internal: true` network, so the DeepSeek TCP connection failed with `ConnectError`.
- Commit `5ef10df` added an API-only egress network and was deployed without recreating Web,
  PostgreSQL or Caddy.
- After that deployment, a fixed synthetic status probe returned DeepSeek HTTP 200. A safe
  envelope probe confirmed: JSON object, one choice, string content, `finish_reason=stop`, bounded
  usage metadata and non-empty Provider reasoning. No content or reasoning text was printed.
- The official live smoke still failed closed as `provider_error` because V4 Flash defaults to
  thinking and its variable reasoning envelope conflicts with the smoke's 4 KiB response bound.
- Commit `df18ce0` explicitly disables thinking, adds a bounded `max_tokens`, and rejects non-stop
  finishes, reasoning content, oversized content and malformed envelopes.

## Verification for `df18ce0`

- DeepSeek Provider and live-smoke focused tests: passed.
- `make format-check`: passed.
- `make lint`: passed.
- `make typecheck`: passed; mypy checked 129 source files.
- `make build`: passed.
- Full `make check`: passed with the existing isolated database
  `foundation_phase0_test`; migration head was `a1b2c3d4e5f6` and metadata drift reported no new
  operations. Contract tests: 13 passed. Web tests: 19 passed.
- The default local database is owned by a different branch state and is not on this branch's
  head. Do not downgrade or reset it; continue using the isolated database if gates must be rerun.

## Exact next actions

1. Push the handoff/current local commits if they are not already on
   `origin/feat/hosted-single-tenant-mvp`.
2. On production, fast-forward exactly from `5ef10df` to the final local branch HEAD.
3. Build and recreate only `api`; assert Web, PostgreSQL and Caddy container IDs are unchanged.
4. Confirm API healthy and local/public HTTPS health 200.
5. Run exactly one repository-defined safe live smoke:
   `ALLOW_PROVIDER_LIVE_SMOKE=1`, fixed synthetic input, no persistence, no raw output.
6. If the smoke passes JSON/schema/semantic validation, resume the existing browser Golden Path
   on `Hosted Pilot Acceptance 2026-07-20`. The already-created SourceAsset/upload/extraction
   operations are idempotent; do not delete the project or database rows.
7. Verify Concept, Script, Storyboard, Shot Plan, Review, Delivery and ZIP download/extraction.
8. Verify logout, post-logout denial, and distinct 401/429/network/5xx UI behavior as applicable.
9. Review safe API/Caddy logs for persistent 500/502/504 without printing sensitive content.
10. Remove the temporary SSH public key and local `/tmp` private/public key files, then issue the
    final production acceptance report.

## Current limitations

- This remains a private single-tenant hosted pilot, not public multi-user authentication.
- Only the approved server-side DeepSeek `deepseek-v4-flash` Adapter is allowed.
- No image/video generation, media rendering, background jobs, cloud object storage, billing,
  Clerk/JWT, organization switching or speculative Stage 20 work is authorized.
- The dependency-owned Starlette TestClient/httpx deprecation warning remains accepted.
