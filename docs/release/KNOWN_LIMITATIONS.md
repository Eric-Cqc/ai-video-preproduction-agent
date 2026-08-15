# Known limitations

## Local RC

The Local RC uses deterministic offline providers, canonical JSON input, and the checked-in
`local_filesystem_v1` object adapter. It has no cloud object storage, production identity provider,
remote AI by default, PDF/DOCX/XLSX rich parsing beyond existing adapters, background jobs, queues,
image/video generation, media rendering, or publishing. The installed Starlette TestClient emits a
dependency-owned deprecation warning; resolving it requires a dependency/lockfile change and is
therefore deferred.

## Hosted pilot truth (Stage 21)

Hosted pilot mechanics exist and were hardened and live-verified in Stage 21: the narrowly
approved ADR-064 server-side DeepSeek adapter now uses server-validated (not hardcoded) endpoint
configuration, bounded retry with backoff, and stable error codes; the private pilot access gate's
rate limiter correctly keys on the proxied client instead of the shared reverse-proxy address; the
Docker Compose topology gives Web and Caddy explicit healthchecks and least-privilege secret
injection (Web no longer receives the full `.env.hosted`); and `make hosted-smoke` now exercises
the real gate/cookie/workflow/ZIP path through the Caddy proxy origin instead of an internal
health check only. `make hosted-backup` exists and was live-verified end to end
(`hosted-build → hosted-up → hosted-bootstrap → hosted-smoke → hosted-backup → hosted-down`, all
exit 0, four healthy containers, no leftover processes).

Hosted acceptance is still **not done**. The ADR-064 privacy, retention, cost, and availability
review record now exists (`docs/hosted/HOSTED_PILOT_REVIEW.md`, `docs/adr/ADR-067`) and is
explicitly **conditional** — live-key activation remains blocked pending external/contractual
criteria (Provider retention terms, external budget/rate controls, PII classification) that no
amount of code hardening can satisfy from inside this repository. CI, ordinary tests, and the
Local RC remain fully deterministic and offline.

## Bounded residuals and access limits

- F-09: storage finalization can precede the database commit. Stage 21 added durable delivery-
  export cleanup on partial failure and an explicit operator `make storage-sweep` command
  (dry-run by default), which reduces the practical impact but does not close the crash window
  itself. This remains the accepted ADR-034 controlled residual.
- **Revision-path transaction residual (new in this record):** provider calls for script/
  storyboard/shot-plan revision still execute inside an open database transaction. Stage 21 moved
  the equivalent calls for concepts/script/storyboard/shot-plan *generation* outside open
  transactions, but explicitly scoped the revision path out as a larger, bundled (up to three
  calls, all-or-nothing) effort. Tracked as a review trigger in ADR-067.
- The Production Desk always submits candidate acceptance with `brief_id: null`, so accepted
  candidates create Brief version 1 of a new Brief lineage; accepting into an existing Brief
  lineage is API-only in this stage.
- Local/test/ci request-context headers are spoofable development context, not authentication.
- The hosted pilot is single-tenant and does not provide production multi-tenant identity,
  collaboration, or authorization.
- No cost ledger or generation quota enforces a budget; Stage 21 added persisted per-call
  provider usage metadata (input/output/total tokens, provider request id), which enables future
  cost attribution but does not itself limit spend. An external Provider-account budget/rate
  control remains an operator responsibility.
- Provider live validation is explicit, external, cost-bearing work and is excluded from
  `make check`.
