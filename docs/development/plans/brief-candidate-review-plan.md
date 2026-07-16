# Brief candidate review plan

Status: implemented and verified — full repository gate passes; staged diff reviewed.

## Frozen decisions

- A human-review candidate remains untrusted until an explicit accept action creates a new draft BriefVersion.
- Review is a small tenant-scoped aggregate with internal `reserved` and terminal `accepted` or `rejected` states. Reservations never survive a failed UoW.
- Accept and reject are idempotent, mutually exclusive, and audited without storing candidate content, prompts, source text, or raw provider output.
- Accept uses the existing Brief CAS and immutable-version lineage. An approved predecessor remains unchanged.

## Milestones

- A — inspect current Brief/Run contracts, document decisions and migration plan.
- B — review domain, persistence constraints, repository and UoW.
- C — accept/reject application service, replay/CAS and API.
- D — PostgreSQL concurrency, rollback, tenant-isolation and API tests.
- E — documentation, migration checks, full validation and staged review.

## Verification coverage

- First-accept and successor rollback matrices cover Brief/Version/Issue/pointer/finalize/Audit failures with no leaked reservation or partial mutation.
- API role coverage proves owner/admin/member mutation, viewer read-only behavior, and one opaque 404 body for inaccessible ownership combinations.
- Canonical digest inputs, terminal-state consistency, same-key concurrency and accept/reject races are checked against PostgreSQL.
- Approved predecessors are compared across every ORM-mapped persistent column before and after successor acceptance.

## Re-evaluation triggers

Add an ADR before reviewer assignment, editing workflows, partial JSON patches, asynchronous review, or automatic promotion of model output.
