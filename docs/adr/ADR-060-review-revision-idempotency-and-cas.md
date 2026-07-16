# ADR-060 — Review and Revision Idempotency and CAS

Status: Accepted for Stage 13

Review submission, revision completion, package creation and export use
tenant/project scoped PostgreSQL reservations keyed by operation and
Idempotency-Key. A matching digest replays the accepted outcome; a changed
digest returns a conflict. Reservation finalization and revision status
updates use compare-and-swap version predicates. Winner rollback leaves no
permanent reservation and permits a loser to take over.
