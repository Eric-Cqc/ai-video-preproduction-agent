# ADR-034: Storage and database consistency

Status: Accepted for Stage 7

## Decision

Use stage → verify → immutable finalize → single database UoW commit. The database transaction contains upload reservation, available object metadata, accepted outcome, and AuditEvent. Database failure after storage finalize triggers deletion compensation. Compensation failure is recorded as a bounded cleanup requirement after rollback and never converted into API success.

PostgreSQL and storage cannot share a transaction; this protocol controls but cannot eliminate crash-window residue. Database success never precedes storage finalize. Repositories do not commit or roll back.

## Re-evaluation triggers

Review when a production adapter provides conditional writes, lifecycle policies, event reconciliation, or when residue SLOs require a background reconciler.
