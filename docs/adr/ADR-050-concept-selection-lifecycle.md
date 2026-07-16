# ADR-050: Concept selection lifecycle

Status: Accepted for Stage 11

Selection is a separate immutable human decision, with one selected candidate per run enforced by database uniqueness and scoped idempotency. Candidate content itself is never changed.
