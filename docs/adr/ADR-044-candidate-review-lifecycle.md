# ADR-044: Candidate review lifecycle

Status: Accepted for Stage 10

Use a tenant-scoped review aggregate for a `human_review_required` Brief extraction candidate. Its internal `reserved` state exists only in the winner transaction; terminal states are `accepted` and `rejected`, and exactly one terminal review may exist for a run.

The reservation, outcome mutation and audit commit atomically. A failed transaction leaves no review row, including no durable `reserved` state.
