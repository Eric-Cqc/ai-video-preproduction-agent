# ADR-046: Candidate review idempotency and CAS

Status: Accepted for Stage 10

Review reservations use PostgreSQL scoped uniqueness and `INSERT ... ON CONFLICT DO NOTHING RETURNING`. Replay is resolved before Brief CAS; same key with a different canonical request digest conflicts.

The digest includes every result-affecting request input: candidate run, action, target Brief/CAS expectations, canonical accepted content, or rejection reason/note. Internal keys and digests are not exposed.
