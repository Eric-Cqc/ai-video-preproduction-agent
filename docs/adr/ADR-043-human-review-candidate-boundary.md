# ADR-043: Human-review candidate boundary

Status: Accepted for Stage 9 foundation

## Decision

Only strict canonical-schema-valid output becomes a candidate run with `human_review_required`. It never creates, updates, submits or approves a BriefVersion. Deterministic RequirementIssue findings are stored as candidate summaries only. A future explicit human workflow must create a new draft BriefVersion through existing immutable/CAS rules.

## Re-evaluation triggers

Review before exposing candidate acceptance, implementing reviewer permissions or creating draft BriefVersions from candidates.
