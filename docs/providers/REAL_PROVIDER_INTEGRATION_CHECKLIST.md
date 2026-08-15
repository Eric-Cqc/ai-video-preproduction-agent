# Real provider integration checklist

Hosted Pilot Phase 1 mechanics exist under [ADR-064](../adr/ADR-064-deepseek-hosted-pilot-provider.md)
and [ADR-066](../adr/ADR-066-single-tenant-hosted-mvp-boundary.md): a narrowly approved,
server-only DeepSeek Adapter, an explicit private single-tenant access gate, and a local-operable
Docker Compose topology. The adapter is JSON-only, bounded, and covered by offline mock transport
tests; the Local RC and CI continue to use the deterministic offline provider.

The hosted pilot is not accepted yet. Before any hosted acceptance, complete the ADR-064 privacy,
retention, cost, and availability review and run the external live end-to-end validation with an
approved key. Live smoke is never part of CI or `make check`. Cloud object storage, production
multi-tenant identity, and broader Provider integrations remain out of scope.
