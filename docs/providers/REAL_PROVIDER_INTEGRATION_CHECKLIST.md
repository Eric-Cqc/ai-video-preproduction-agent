# Real provider integration checklist

Hosted Pilot Phase 1 mechanics exist under [ADR-064](../adr/ADR-064-deepseek-hosted-pilot-provider.md)
and [ADR-066](../adr/ADR-066-single-tenant-hosted-mvp-boundary.md): a narrowly approved,
server-only DeepSeek Adapter, an explicit private single-tenant access gate, and a local-operable
Docker Compose topology. The adapter is JSON-only, bounded, and covered by offline mock transport
tests; the Local RC and CI continue to use the deterministic offline provider.

The Stage 21 hosted-hardening work closed the mechanical gaps found at first review: configured
base URL/model are now actually used (not silently ignored), generation-flow provider calls run
outside open database transactions with bounded failure finalization, retries are bounded with
backoff and a wall-clock deadline, error codes are stable, and `make hosted-smoke` now exercises
the real gate/cookie/workflow/ZIP path through the Caddy proxy origin. See
[HOSTED_PILOT_REVIEW.md](../hosted/HOSTED_PILOT_REVIEW.md) and
[ADR-067](../adr/ADR-067-hosted-pilot-review-outcome.md) for the full record.

The hosted pilot is still not accepted for a live key. Before live-key activation, complete the
external/contractual criteria in `HOSTED_PILOT_REVIEW.md` (Provider retention terms, external
budget/rate controls, approved data classification, tested backup/restore) and run the external
live end-to-end validation with an approved key. Live smoke is never part of CI or `make check`.
Cloud object storage, production multi-tenant identity, and broader Provider integrations remain
out of scope.
