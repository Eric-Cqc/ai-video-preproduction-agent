# Current project handoff

Generated: 2026-07-21 Asia/Hong_Kong.

## Resume objective

Resume Tencent Cloud production acceptance at the existing signed-in Production Desk. The
Provider network and structured-output defects are fixed and the repository-defined safe
DeepSeek live smoke has passed. Do not redeploy, rerun the live smoke, recreate the test project,
run migrations, or restart PostgreSQL/Caddy. Continue the existing synthetic Golden Path, verify
the Delivery ZIP and session/logout behavior, inspect only safe logs, then remove the temporary
acceptance SSH key.

## Repository and production state

- Local repository: `/Users/caiqichong/Developer/ai-video-preproduction-agent`
- Production repository: `/home/ubuntu/ai-video-preproduction-agent`
- Branch: `feat/hosted-single-tenant-mvp`
- Deployed application HEAD: `e81dfcb575e3ec59006951ab37a2b2eabf20021c`
- This handoff is a documentation-only descendant of `e81dfcb`; it does not require a production
  deployment. Confirm `e81dfcb` is an ancestor of the local/origin branch tip rather than resetting
  the branch to the deployed application commit.
- Local and production working trees: clean when this checkpoint was started
- Migration head: `a1b2c3d4e5f6`; no migration is pending
- Domain: `app.gemaogejiaojiao.cn`
- API health: public HTTPS 200
- Web: public HTTPS 200
- Production Compose file: `infra/docker/compose.hosted.yml`
- Compose services: `api`, `web`, `postgres`, `caddy`
- API: running and healthy; attached to `internal` and `provider_egress`
- PostgreSQL: running and healthy; internal-only
- Web: running; internal-only
- Caddy: running; the only public ingress, with TCP 80/443 published

Relevant commits, oldest first:

1. `fa467e4 fix: restore hosted pilot access`
2. `1273c38 fix: keep hosted secrets out of web`
3. `5ef10df fix: allow hosted provider egress`
4. `df18ce0 fix: bound DeepSeek structured output`
5. `64ca6bb docs: checkpoint hosted acceptance`
6. `e81dfcb docs: clarify hosted checkpoint head`

The latest production update rebuilt and recreated only `api`; Web, PostgreSQL and Caddy were not
recreated by that update. Production HEAD and all four service states were rechecked immediately
before this handoff revision.

## Security state

- The previously exposed pilot password and session-signing secret were rotated successfully.
- Production login using the rotated credential passed. Do not ask for, inspect, copy or report
  the credential again.
- Never inspect or print `.env.hosted`, container environment values, cookies, tokens, Provider
  keys, Prompts, raw Provider responses or reasoning content.
- Web receives only an explicit non-secret runtime allowlist; production verification reported
  `WEB_SECRET_ISOLATION=pass`.
- A temporary acceptance SSH key remains installed for `ubuntu` with comment
  `codex-video-agent-acceptance-2026-07-21`. The local private key is
  `/tmp/codex-video-agent-deploy-key` and the public key is the same path with `.pub` appended.
  Remove the matching server `authorized_keys` line and both local files only after all acceptance
  work is complete.

## Verification completed

- `make format-check`, lint, typecheck and build passed; mypy checked 129 source files.
- Full `make check` passed against the isolated `foundation_phase0_test` database. Migration head
  was `a1b2c3d4e5f6`, metadata drift reported no new operations, Contract tests were 13 passed and
  Web tests were 19 passed. The aggregate command exited zero.
- The default local database belongs to another branch state. Do not downgrade or reset it; use
  the isolated database only if gates must be rerun.
- Production API, local HTTPS health, public HTTPS health and Web all passed after the API-only
  deployment.
- The repository-defined safe live smoke passed with Provider `deepseek`, model
  `deepseek-v4-flash`, capability `structured-brief`, accepted authentication, valid JSON, schema
  validation, semantic validation and safe usage metadata. Recorded safe usage was 619 input,
  544 output and 1163 total tokens. No raw Prompt, response or reasoning was printed or persisted.

## Existing Golden Path state

- Production browser session is authenticated; a reload retained the session.
- Project list currently reports one project.
- Existing synthetic project: `Hosted Pilot Acceptance 2026-07-20`, status `draft`.
- The project is visible but not selected. The detail panel still displays the instruction to
  choose a project. No Golden Path action was clicked after the latest API deployment.
- The project contains only synthetic acceptance data. Its earlier SourceAsset, upload and parse
  steps succeeded. The earlier Brief run failed before the network/output fixes; keep those audit
  records and rerun through the UI rather than deleting rows.
- Synthetic upload fixture:
  `packages/test-fixtures/brief/valid-structured-brief-v1.json`
- Product-client source/upload/parse operations are idempotent for the same project. Brief
  extraction creates a new run and should now exercise the fixed real Provider path.

## Exact next actions

1. Do not deploy the documentation-only handoff commit. Reconnect to the existing browser session
   at `https://app.gemaogejiaojiao.cn/` and confirm the
   user is still authenticated. Do not inspect cookies or browser storage.
2. Select `Hosted Pilot Acceptance 2026-07-20` from the one-item project list.
3. Upload `packages/test-fixtures/brief/valid-structured-brief-v1.json` through the
   `Structured Brief JSON` chooser, then click `开始 Golden Path` once.
4. Observe every stage without printing Provider content: Brief candidate acceptance, Concept,
   Script, Storyboard, Shot Plan, Review approval, Delivery and ZIP export.
5. If a stage fails, use safe status fields, correlation IDs and bounded API/Caddy log inspection.
   Do not inspect secrets, Prompt text, raw Provider output or reasoning.
6. Download the ZIP, verify non-zero size, successful extraction, sane filenames/encoding and the
   expected Brief, Concept, Script, Storyboard and Shot Plan deliverables.
7. Confirm the workflow used `deepseek-v4-flash` from safe operation metadata and that accepted
   artifacts were persisted. Do not run another standalone live smoke unless diagnosing a new
   failure requires it.
8. Refresh once to verify the authenticated session remains valid. Then sign out, verify the login
   screen returns, protected project data is unavailable and post-logout access is denied.
9. Review bounded, redacted production logs for persistent 500/502/504 responses or accidental
   secret/raw-content leakage.
10. Remove the temporary SSH public-key line from the server and delete the local private/public
    key files. Verify the temporary key no longer authenticates.
11. Update this handoff to final acceptance evidence, then issue the production acceptance report.

## Current limitations

- This is a private single-tenant hosted pilot, not public multi-user authentication.
- Only the approved server-side DeepSeek `deepseek-v4-flash` Adapter is allowed.
- No image/video generation, media rendering, background jobs, cloud object storage, billing,
  Clerk/JWT, organization switching or speculative Stage 20 work is authorized.
- The dependency-owned Starlette TestClient/httpx deprecation warning remains accepted.
