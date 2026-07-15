# Contracts

This directory owns cross-language API contracts. `schemas/health-v1.schema.json` is the single canonical health contract, and `schemas/structured-brief-v1.schema.json` is the single canonical Structured Video Brief contract. Python and TypeScript consumers validate at their boundaries against these files; their thin language representations are tested with the same deterministic fixtures.

Contract versions use semantic versioning. Additive compatible changes require a minor version and compatibility tests. Breaking changes require a new schema file, migration/deprecation notes, and an ADR; an accepted schema is never silently overwritten.
