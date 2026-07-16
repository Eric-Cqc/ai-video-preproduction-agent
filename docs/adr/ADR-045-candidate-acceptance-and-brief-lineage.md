# ADR-045: Candidate acceptance and Brief lineage

Status: Accepted for Stage 10

Accepting a candidate creates a new draft BriefVersion through existing Brief CAS. It creates a Brief/version 1 when none exists, otherwise a successor pointing at the current version. Approved predecessors remain completely unchanged.

Successor acceptance conditions the aggregate update on both aggregate version and current-version pointer. The approved-predecessor guarantee covers every persisted predecessor column, not only lifecycle fields.
