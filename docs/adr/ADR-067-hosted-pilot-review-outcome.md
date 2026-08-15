# ADR-067: Hosted pilot review outcome and activation gate

Status: Proposed — conditional acceptance record; live key not yet authorized.
Date: 2026-08-15 (Stage 21).
Related decisions: ADR-064, ADR-066.
Numbering: ADR-065 is absent; ADR-066 remains unchanged. This is the next free ADR number.

## Context

ADR-064 authorized a narrowly scoped server-side DeepSeek adapter but required a separate
privacy, retention, cost, rate-limit, availability, and failure-behavior review before hosted
acceptance. Stage 20 produced the local Truthful RC; Stage 21 hardened the adapter, reliability,
and hosted-validation mechanics that this review depends on.

The required review is recorded in [HOSTED_PILOT_REVIEW.md](../hosted/HOSTED_PILOT_REVIEW.md).

Stage 21 closed several mechanical gaps identified at the first review pass: configured
base URL/model are now actually used (not silently ignored), provider calls for four of five
generation flows now execute outside open database transactions, failures finalize into a bounded
`failed` state instead of leaking `reserved` operations, retries are bounded with backoff and a
wall-clock deadline, error codes are stable, `requested_changes` is bounded, provider usage is
persisted, delivery-export cleanup is durable, an operator storage-sweep command exists, the
hosted proxy smoke now exercises the real gate/cookie/workflow/ZIP path instead of only an
internal health check, and the pilot rate limiter is no longer collapsed by the reverse proxy.

The repository still does not contain Provider-side retention terms, an application PII/redaction
control, a cost enforcement mechanism, or a fix for the revision-path transaction residual.

## Decision

Record the ADR-064 review outcome as **conditional and not yet accepted for a live key**, updated
from the pre-Stage-21 baseline to reflect the mechanical hardening completed this stage.

The code boundary is considered suitable only for a private, single-tenant, explicitly approved
pilot using synthetic or otherwise approved non-sensitive material, and only after every
activation criterion in `HOSTED_PILOT_REVIEW.md` is evidenced.

This ADR does not modify ADR-064 or ADR-066 and does not authorize: a public or multi-user
deployment; production-grade identity; a second Provider; cloud object storage; billing or
customer chargeback; image/video generation or media rendering; background jobs, queues, or
distributed services; automatic production fallback; processing of PII, regulated data, secrets,
or unapproved customer material.

## What hosted pilot acceptance means

Unchanged from ADR-064/ADR-066: one private Compose deployment, one configured
Organization/Workspace, one pilot actor behind the non-production password gate, the server-side
`deepseek-v4-flash` adapter at the exact approved (now server-validated, not hardcoded) endpoint,
credentials held only by the API service, deterministic offline mode retained as default/kill-
switch, and no automatic media generation, rendering, publishing, or distribution.

## Review findings

### Accepted technical boundary (frozen, now stronger)

- Exact, server-validated endpoint and model (Stage 21 closed the "validated but ignored"
  configuration gap).
- Server-only Provider call; no browser Provider access; no tools/browsing/file access.
- Bounded adapter input/output checks, now with bounded retry backoff and a wall-clock deadline.
- Four of five generation flows now call the provider outside any open database transaction.
- No raw prompt or raw provider response persistence; provider usage metadata is persisted
  additively without appearing in audit payloads.
- Durable delivery-export cleanup and an explicit, non-scheduled operator sweep command.
- Hosted proxy smoke exercises the real gate, cookie, full workflow, replay/conflict, tenant
  isolation, and ZIP integrity through the actual reverse-proxy origin.
- The pilot rate limiter now keys on the correct client hop in hosted mode instead of the shared
  proxy address.

Evidence: `docs/development/plans/stage-21-hosted-validation-contract.md`,
`docs/hosted/HOSTED_PILOT_REVIEW.md`.

### Conditional or unresolved controls (unchanged from the ADR-064 requirement)

- Provider-side retention, training, region, subprocessors, deletion, and incident terms.
- PII/secret handling in source text and structured artifacts.
- Application cost ledger and generation quotas (usage is now recorded; nothing enforces a limit).
- Hosted log and audit-integrity controls; single-node availability.
- **The revision path (script/storyboard/shot-plan bundle revision) still issues its provider
  calls inside an open database transaction.** This was explicitly scoped out of Stage 21 as a
  Large-effort item (bundling up to three calls with all-or-nothing semantics); it remains a
  known, documented residual and a review trigger for the next hardening stage.

## Consequences

The pilot may remain operationally useful for controlled, approved data, but it must not be
described as a production AI service, a zero-retention Provider integration, or a cost-bounded
service. The operator must maintain external Provider-account budget and rate controls. Backups
now have a verified, working command (`make hosted-backup`, live-tested in Stage 21); restore has
not itself been live-tested end to end and remains an operator responsibility per the runbook.

## Activation gate

Unchanged from `HOSTED_PILOT_REVIEW.md`'s explicit checklist. All criteria remain mandatory;
Stage 21 satisfied none of the external/contractual criteria (those require action outside this
repository) and closed the previously-open mechanical/technical criteria (server-validated
config, bounded retries, stable error codes, transaction-boundary correctness for 4/5 flows,
durable cleanup, real proxy smoke, correct rate-limit key).

## Re-evaluation triggers

Unchanged from the ADR-064 requirement, plus one Stage-21-specific addition:

1. Provider terms, model, endpoint, SDK, request schema, retry behavior, or limits change.
2. Any PII, regulated data, secrets, customer-confidential material, or external collaborator
   enters the pilot.
3. The deployment becomes public, multi-user, shared, or production-grade.
4. A second Provider, cloud object store, identity system, queue, worker, replica, or billing
   system is introduced.
5. Cost, quota, rate-limit, retention, privacy, security, or availability incidents occur.
6. The application adds PII detection, redaction, deletion, retention jobs, usage-based
   enforcement, automatic fallback, or new Provider persistence.
7. The pilot is closed and its database, object volumes, backups, or Provider-side data require
   disposal or deletion.
8. **The revision-path transaction residual is addressed** — update `HOSTED_PILOT_REVIEW.md` and
   this ADR's findings table when that work lands; do not silently let the review go stale.

## Supersession

This ADR records the review outcome and activation gate. It does not amend or renumber ADR-064
or ADR-066.
