# ADR-042: Immutable AI extraction runs and attempts

Status: Accepted for Stage 9 foundation

## Decision

Persist immutable tenant-scoped BriefExtractionRun and BriefExtractionAttempt records. Runs reference an immutable DocumentExtraction and record provider/model/template/input provenance. Attempts classify success, malformed output, schema invalidity, refusal, timeout or provider error. Raw prompts, full inputs and raw outputs are not persisted.

## Re-evaluation triggers

Review for retries, multiple attempts, asynchronous execution, retention or cost/token telemetry.
