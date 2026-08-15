# Current Truth and Next Stage

This document records the truth-first audit that triggered Stage 20 and the verified state after
Stage 20 completed. Method: five independent read-only audit passes (product golden path, backend
correctness/tenancy, test/CI/release, frontend/UX, architecture/roadmap), an adversarial red-team
review, and real-host verification of every claimed pass. Only evidence-backed conclusions are
recorded.

## Part 1 — Pre-Stage-20 baseline audit (2026-08-15, historical)

At the audit snapshot (main@79209e4, Stages 1–19 merged) the honest classification was:

- Backend (API/database/storage/lineage): genuine Local-RC maturity. Every golden-path step ran a
  real HTTP route → application service → Unit of Work → repository → storage path with audit and
  immutable versions. No tenant-isolation escape was found.
- Frontend (Production Desk): a demo façade. One screen with a one-click batch runner that
  auto-accepted the Brief candidate, auto-selected the first concept, and auto-approved the
  planning bundle — contradicting the product's own human-review boundary (ADR-043/ADR-058) and
  the README.
- Release path: `rc-smoke` was in-process (TestClient), not socket-level; a fresh environment
  could not complete the quickstart (missing `make setup` step; the test database was never
  migrated by any local target; RC ports/CORS were not propagated).
- Backend correctness: seven P1 defects — replay resolved before membership authorization,
  replay payloads mixing historical and current state, non-idempotent unaudited cancellation,
  stale loser reads under concurrent completion, missing Brief-aggregate audit on candidate
  acceptance, streaming downloads that could emit 200 before storage failures, and no server-side
  idempotency for Brief extraction runs.
- Hosted MVP Phase 1: adapter/access-gate/compose mechanics exist, but the ADR-064-required
  privacy/retention/cost/availability review and live-chain acceptance remain outstanding.

## Part 2 — Stage 20 outcome (verified post-implementation)

Stage 20 ("Truthful Local RC", contract:
`docs/development/plans/stage-20-truthful-local-rc-contract.md`) closed the gap between backend
truth and product truth. All work is currently uncommitted on `main@79209e4`.

### What changed

- Backend correctness (WS-A, A1–A7): authorization now precedes replay resolution on every
  mutation path; replay responses are self-consistent and legacy (pre-snapshot) operations are
  explicitly marked instead of fabricating values; revision cancellation is a first-class
  idempotent, audited operation; concurrent completion losers re-read committed winner state
  (bypassing the ORM identity map); candidate acceptance writes Brief-aggregate audit events;
  streaming exports verify the first chunk before any 200 is sent; Brief extraction accepts an
  optional `Idempotency-Key`. Three new migrations; head `d5e6f7a8b9c0`; downgrade guards refuse
  data-destructive paths.
- Production Desk (WS-B): a stage-aware project workspace with real, explicit human gates —
  candidate review (accept/reject with requirement issues), side-by-side concept selection,
  per-stage generation actions, bundle approval or revision request with completion/cancellation,
  delivery only after approval. Artifacts render as readable product surfaces (formatted brief,
  concept cards, script view, storyboard cards, shot-plan table, delivery manifest with export
  checksum); raw JSON is a secondary inspect toggle. Same-browser resume via stored artifact IDs
  revalidated against server GETs; unverifiable browser state is shown as unverified, never as
  server truth; in-flight mutations cannot contaminate another project; API error envelopes
  (code, message, correlation id) and 409 recovery paths are surfaced.
- Release truth (WS-C): `make rc-smoke` is now a socket-level smoke against a running API and Web
  (full API workflow incl. replay/conflict, viewer denial, cross-tenant 404, ZIP
  membership/manifest/checksum; Web health/render check — browser interaction is verified
  manually); the previous in-process suite is preserved as `rc-golden-path-test`; `rc-up`
  migrates both databases, propagates ports/CORS, and traps failures; `rc-check` runs an isolated
  socket cycle on 18001/13001 with `foundation_test`; documentation was reconciled to match.

### Verified state (real host, 2026-08-15)

- `make check`: PASS — 395 Python, 13 contract, 30 Web tests, production Web build.
- `make rc-up` → `rc-seed` → `rc-smoke` → `rc-down`: PASS (socket-level).
- `make rc-check`: PASS; no leftover processes on RC ports.
- Migration downgrade ×2 / upgrade to head on `foundation_test`: PASS.
- Rendered Production Desk (server-side) with stage rail and explicit gates: verified.

### Classification after Stage 20

**Truthful Local RC.** The interactive golden path is real end to end, human decision gates are
enforced in both server and UI, and the release commands verify what they claim. It is not a
hosted MVP: the ADR-064 product review (privacy/retention/cost/availability) and live-provider
chain acceptance remain open product decisions, single-tenant pilot access is explicitly
non-production authentication, and the worker remains a self-check boundary with no job handlers.

## Next stage (single recommendation)

**Hosted Pilot Validation and Operational Hardening** — keep the single-tenant boundary,
deterministic defaults, and the one authorized DeepSeek adapter; complete the ADR-064-required
review record; validate the full hosted chain (gate → workflow → delivery) with synthetic and
explicitly authorized pilot data; collect real-user evidence before any architectural expansion.
Known accepted residuals for that stage's planning: storage finalize precedes DB commit
(ADR-034 residual, orphan-object window), broad repository exception mapping to 409, provider
calls inside open transactions, and delivery cleanup without a durable ledger.
