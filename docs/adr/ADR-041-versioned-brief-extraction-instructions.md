# ADR-041: Versioned Brief extraction instructions

Status: Accepted for Stage 9 foundation

## Decision

Use a versioned instruction template that requires raw Structured Brief JSON, forbids tools/URL fetch/code execution, and marks extracted document text as untrusted data. Persist template identifier/version, not the full rendered prompt.

## Re-evaluation triggers

Review whenever instructions, canonical schema, provider capabilities or evaluation expectations change.
