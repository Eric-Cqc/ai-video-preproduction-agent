# Hosted Pilot Review — ADR-064 Required Record

Status: Conditional review; live-key acceptance remains blocked pending the criteria below.
Review date: 2026-08-15 (Stage 21).
Scope: ADR-064 DeepSeek hosted pilot within the ADR-066 single-tenant hosted MVP boundary.

This record describes actual repository behavior after Stage 21 hardening. It does not establish
DeepSeek contractual terms, provider-side retention, deletion, training use, geographic
processing, or incident notification obligations — those remain externally verified facts, not
code facts.

Evidence labels: FACT (code/doc evidence), ASSUMPTION (operational assumption needing
confirmation), GAP (not implemented / not evidenced).

## Review outcome

The code supports a narrowly bounded, server-side DeepSeek adapter:

- exact endpoint and model, now passed in from validated server configuration rather than
  hardcoded (Stage 21 P1/F-27 fix) — `services/api/app/application/model_provider.py:57-90`,
  `services/api/app/main.py` provider wiring.
- no browser Provider call; no tools, browsing, URL/file access, redirects, or inherited proxy
  settings.
- bounded input and successful-response body limits; bounded retry with backoff and a total
  wall-clock deadline across attempts (Stage 21 P3).
- stable provider error codes surfaced through the API envelope instead of a generic
  `invalid_request` (Stage 21 P4).
- schema and semantic validation before accepted persistence; bounded `requested_changes` size
  and nesting depth (Stage 21 P5).
- provider calls for concepts/script/storyboard/shot-plan now execute outside any open database
  transaction, matching the brief-extraction pattern (Stage 21 P6) — reservation commits, the
  transaction closes, the provider call happens with no DB transaction open, then a second
  transaction re-authorizes and finalizes accepted or failed.
- provider usage metadata (input/output/total tokens, provider request id) is now persisted
  additively on the run/operation rows (Stage 21 P2); audit payloads still never contain prompts,
  raw responses, or usage figures.
- durable delivery-export cleanup on partial failure (Stage 21 R2) and an explicit operator
  `make storage-sweep` command (Stage 21 R3) reduce — but do not eliminate — the residual orphan-
  object crash window (F-09, still an accepted ADR-034 residual).

The review does not approve a live key yet. The following remain blocking unknowns or gaps:

- provider-side prompt/response retention and training-use terms (external, unverifiable from
  this repository);
- application-level PII or secret detection/redaction (not implemented; operating rule below
  substitutes for a technical control);
- application retention, deletion, and staging-file cleanup remain manual/operator-triggered
  (`make storage-sweep`), not automatic;
- no budget ledger or hard per-tenant/per-day generation quota (usage is now persisted per call,
  but nothing enforces a limit from it);
- no successful-call rate/concurrency control beyond the pilot-password limiter;
- the revision path (script/storyboard/shot-plan bundle revision) still issues its provider
  calls inside an open transaction — this is a **documented, deliberate Stage 21 residual**
  (P6 explicitly excluded it: bundling up to three calls with all-or-nothing semantics made the
  split Large/out of bounded scope). Track under the same F-19 review trigger as future work.

### Post-review-pass corrections (same stage)

An independent red-team pass found and this stage fixed five additional issues before
acceptance, each re-verified live on a real Docker host after the fix:

1. The retry deadline was a single `timeout_seconds` shared across all attempts, not
   `timeout × attempts` as specified — a slow first attempt could starve every retry. Fixed:
   `total_timeout_seconds = timeout_seconds * max_attempts`, with each attempt capped at
   `min(remaining, timeout_seconds)`. httpx's inactivity-based timeout means a continuously
   trickling response can still exceed the deadline in principle — a documented, accepted
   transport residual bounded by the attempt cap, not eliminated.
2. The stale-reservation takeover threshold was an independent constant that could be shorter
   than a legitimate in-flight call's worst-case duration, risking a duplicate paid provider
   call. Fixed: the threshold is now derived from the provider's own `total_timeout_seconds` plus
   a safety margin, and every takeover now writes a bounded audit event
   (`error_code: stale_reservation_reclaimed`) instead of silently overwriting the reservation.
3. `requested_changes` bounds (size/depth) were enforced only at the presentation/pydantic layer,
   not the application layer — bypassable by direct service callers and unenforced against
   pre-Stage-21 legacy rows at completion time. Fixed: enforcement now also happens in the
   application layer at submission and again at completion.
4. `make storage-sweep --apply` deleted files based on a one-time reference snapshot with no
   minimum grace period, risking deletion of an object finalized to storage just before its
   database row commits. Fixed: a 1-hour minimum grace period is enforced, and the reference
   check is re-run immediately before each individual file deletion, not just once at the start.
5. The API container was mounted the entire `caddy_data` volume (including Caddy's private TLS
   material) just so the hosted smoke script could read one public root CA certificate. Fixed:
   the mount was removed entirely; the local-validation smoke path now defaults to
   `HOSTED_SMOKE_INSECURE=1` for `localhost`/`127.0.0.1` origins instead of sharing any Caddy
   volume with the API container.

Additionally, the hosted proxy smoke's "viewer denial" assertion was found to test the wrong
thing (that hosted mode rejects temporary impersonation headers, not that a viewer-role session
cannot mutate) — the single-actor, cookie-based pilot access model has no mechanism to
authenticate as a second, viewer-role actor, so that coverage was corrected to accurately
describe what is and is not tested (see the code comment in `hosted_proxy_smoke.py`; viewer-role
RBAC denial is covered at the application/API test layer, not by this hosted smoke). The
bootstrap-idempotency assertion was strengthened to genuinely invoke bootstrap twice and compare
organization/workspace identity and owner-membership snapshots, rather than only reading state
once.

Evidence: `docs/adr/ADR-064-deepseek-hosted-pilot-provider.md:19-24`,
`docs/adr/ADR-066-single-tenant-hosted-mvp-boundary.md:21-26`,
`docs/development/plans/stage-21-hosted-validation-contract.md`.

## Data flow inventory

### Provider boundary

FACT: The application creates one server-side adapter with a fixed HTTP client. The request is
sent to the configured (validated) DeepSeek endpoint with:

- `Authorization: Bearer <DEEPSEEK_API_KEY>`;
- a fixed `User-Agent`;
- a JSON body containing `model` (server-validated, not client-selected), `response_format`,
  `stream: false`, and two messages (fixed system instructions + untrusted-data-wrapped input).

`tools` and `tool_choice` are absent. Redirects and environment proxy inheritance are disabled.
`DEEPSEEK_API_KEY` is sent only as an HTTP authorization header to DeepSeek; it is never sent to
browser code, JSON payloads, application logs, audit payloads, or persistence.

### Application calls and transmitted content

| Operation | Content sent to the adapter | Fixed instructions | Provider call location |
| --- | --- | --- | --- |
| Structured Brief extraction | `DocumentExtraction.extracted_document["text"]` only | Structured Brief schema rules + fictional example | Outside any open transaction (unchanged since Stage 20) |
| Creative concepts | Canonical `BriefVersion.structured_content` JSON | "Return exactly three JSON concept objects..." | Outside any open transaction (Stage 21 P6) |
| Script generation | Selected concept content | "Return one Script JSON object..." | Outside any open transaction (Stage 21 P6) |
| Storyboard | `{"kind":"storyboard","script":<content>}` | "Produce structured storyboard JSON only..." | Outside any open transaction (Stage 21 P6) |
| Shot plan | `{"kind":"shot_plan","storyboard":<content>}` | "Produce structured shot plan JSON only..." | Outside any open transaction (Stage 21 P6) |
| Revision (script/storyboard/shot-plan, up to 3 calls per bundle) | `{"artifact":<source>,"requested_changes":<bounded>}` | Revision JSON-only instruction | **Inside an open transaction — documented residual, not fixed this stage** |

`requested_changes` is now bounded (Stage 21 P5): capped serialized size and nesting depth,
rejected with 400 before reaching the provider if oversized.

### What is never sent to DeepSeek

Unchanged from the prior review: original uploaded bytes, filenames, checksums, storage keys,
internal tenant/actor/correlation/idempotency IDs, review summaries, client-selected model/tools,
and raw provider responses are never included in the adapter payload or persisted.

### Runtime caps

FACT (Stage 21 additions in bold):

- `DEEPSEEK_TIMEOUT_SECONDS` ≤ 60s; `DEEPSEEK_MAX_ATTEMPTS` ≤ 2 (unchanged).
- **Bounded backoff between attempts, honoring `Retry-After` up to a cap, and a total wall-clock
  deadline across attempts so a second attempt cannot start once the budget is exhausted (P3).**
- Input/output byte caps unchanged (131072 / 262144 bytes in the example config).
- **`requested_changes` is capped in serialized size and nesting depth (P5).**
- GAP (unchanged): the input-byte cap excludes system instructions, wrapper markers, and JSON
  overhead; no provider-side `max_tokens`/output-token cap is sent.

## Privacy

Unchanged from the prior review: the DeepSeek exposure surface includes canonical extracted
source text, full structured Brief content, selected concept/script/storyboard content, and
revision `requested_changes`. No general PII classifier or secret scanner inspects this content.

**Pilot operating rule (unchanged):** until a separate privacy approval exists, pilot users must
not upload secrets, identity/health/financial data, regulated personal data, or unapproved
customer/confidential material. This is an operating rule, not a technical enforcement claim.

Log and audit hygiene: unchanged and re-verified — the JSON log formatter and audit writers do
not emit prompts, source text, raw provider responses, or now-persisted usage figures.
**Provider usage metadata (P2) is stored on run/operation rows, not in audit payloads.**

## Retention

Unchanged database/local-storage retention story from the prior review, with two Stage 21
additions:

- **Delivery export cleanup on partial failure is now durable** (R2): a failed delete is recorded
  in `delivery_export_cleanup_requirements` instead of silently discarded.
- **An explicit, operator-triggered `make storage-sweep` command exists** (R3): dry-run by
  default, requires an explicit apply flag, protects all referenced storage keys, processes
  durable cleanup rows first, and never runs as a background scheduler (frozen boundary
  respected — no queue/daemon was introduced).

Provider-side retention statement: still **not verified**. No repository evidence establishes
DeepSeek prompt/response retention duration, training use, region, subprocessors, or deletion
SLA. This remains an unknown risk and a blocking live-key acceptance item.

## Cost and rate exposure

FACT (Stage 21 changes):

- Provider usage (input/output/total tokens, provider request id) is now persisted per
  successful call (P2) — this enables future cost attribution but **does not itself enforce a
  budget**. No budget ledger, quota, or successful-call rate limiter exists yet.
- Retries now have bounded backoff and a wall-clock deadline (P3), reducing (not eliminating)
  worst-case duplicate-attempt cost exposure.
- A planning-bundle revision can still make up to three separate calls in one open transaction
  (documented residual, unchanged cost shape).

The live pilot still requires an external Provider-account budget, rate limit, alert, and manual
stop procedure before activation — the application has usage data now, but no enforcement.

## Availability and failure modes

FACT (Stage 21 changes):

- Adapter failure classification (timeout/refusal/error) is now surfaced through **stable,
  specific error codes** at the API boundary for concepts/script (P4), rather than folding into a
  generic `invalid_request`.
- Concepts/script/storyboard/shot-plan generation failures now finalize the reservation as
  `failed` in a bounded second transaction (P6) instead of leaving it `reserved` indefinitely;
  stale reservations are recoverable on a later request with the same idempotency key.
- No automatic degradation from DeepSeek to deterministic mode still exists; the kill-switch
  remains a manual `MODEL_PROVIDER=deterministic_offline` environment flip and restart
  (documented in `docs/hosted/OPERATIONS_RUNBOOK.md`).
- Single-node Compose limits are unchanged; Web and Caddy now have explicit healthchecks
  (Stage 21 V1), improving detectability of a stuck container but not adding redundancy.

## Incident response

See `docs/hosted/OPERATIONS_RUNBOOK.md` §8 for exact, verified commands (key rotation, gate
disable, deterministic fallback, backup-based recovery). That runbook is the operational source
of truth; this section records only the review-level obligations:

1. Contain: stop the public Caddy service.
2. Fall back: flip to `MODEL_PROVIDER=deterministic_offline`.
3. Rotate: revoke and replace the DeepSeek key at the issuer; rotate pilot secrets if the gate is
   implicated (Stage 21 V4 changed the gate's rate-limit key derivation, not its rotation
   procedure — rotation steps are unchanged).
4. Investigate using bounded, secret-free logs only.
5. Notify the pilot owner, Security, Privacy/Legal, and DeepSeek per contract terms.

## Residual risks

| Risk | Status after Stage 21 | Owner | Trigger for action or re-review |
| --- | --- | --- | --- |
| Provider retention, training use, region, subprocessors unknown | Unchanged — still unverified | Privacy/Legal + pilot owner | Any live-key request |
| Source text may contain PII or secrets | Unchanged — no scan, operating rule only | Product owner | Any non-synthetic/regulated upload |
| No application purge or TTL | Improved — `make storage-sweep` exists but is manual, not scheduled | Operations | Customer deletion request, pilot closure, disk pressure |
| No cost ledger / budget enforcement | Partially improved — usage now persisted, no enforcement | Fable + Finance/Operations | Unexpected bill, 429, or quota event |
| Revision path provider calls remain inside open transactions | **Unchanged — documented Stage 21 residual, not fixed** | Fable | Revision latency/availability incident, or next hardening stage |
| F-09 orphan-object crash window | Improved — durable cleanup (R2) + sweep (R3), window itself not closed | Operations | Repeated orphan objects observed in sweep output |
| RC/hosted operational PID-reuse false-positive | **Fixed and live-verified this stage** (port-descendant ownership check) | — | Reopen only if a future environment lacks `lsof` |
| Pilot password gate is not production identity | Unchanged | Product owner | External collaborators, public rollout |
| Rate limiter collapsed by reverse proxy | **Fixed this stage** — hosted mode now keys on the first `X-Forwarded-For` hop from Caddy (V4) | Operations | Any future additional proxy hop |

## Explicit acceptance criteria for turning the pilot ON with a live key

Unchanged from the ADR-064 requirement; all remain mandatory and none are satisfied by Stage 21
alone (Stage 21 hardened the *mechanism*, not the *external/contractual* preconditions):

- [ ] ADR-067 is approved by the pilot owner.
- [ ] Current DeepSeek contractual documentation confirms retention, training use, region,
      subprocessors, deletion, and incident-notification terms.
- [ ] Approved data classification is synthetic or explicitly non-sensitive; no PII/secrets.
- [ ] Exact server-only DeepSeek configuration is verified in the live environment.
- [ ] An external Provider-account budget/rate limit and alert owner exist.
- [ ] Encrypted, access-controlled backups exist and restore has been tested
      (`make hosted-backup` now exists and was verified in Stage 21 — restore procedure is
      documented in `OPERATIONS_RUNBOOK.md` but has not itself been live-tested end to end).
- [ ] The separately authorized live smoke (`infra/scripts/provider_live_smoke.py`) passes
      outside CI with `ALLOW_PROVIDER_LIVE_SMOKE=1`.
- [ ] The deterministic kill-switch has been exercised.
- [ ] Named incident owner, escalation path, and key-rotation contacts are available.
- [ ] The deployment remains one private tenant within the ADR-066 boundary.

Activation decision: all boxes checked → private pilot may be turned ON with a live key. Any box
unchecked or unknown → live key remains OFF; deterministic mode remains the only accepted hosted
mode.

## Review triggers

Unchanged from the ADR-064 requirement (see ADR-067 for the consolidated list). Reopen this
review before: Provider terms/endpoint/model change; PII/regulated data enters scope; the
deployment becomes public/multi-user; cost/rate/availability incidents occur; the revision-path
transaction residual is finally addressed (update this record when it is); cloud storage,
identity, queues, or a second Provider are introduced.
