# ADR-038: Parsing resource and content safety

Status: Accepted for Stage 8

## Decision

Cap parser input at 5 MiB and normalized output at 1 MiB/characters. Accept strict UTF-8 with optional BOM, normalize newlines, reject NUL/disallowed controls and binary masquerade. CSV permits at most 10,000 rows and 100 columns. JSON permits depth 32 and 100,000 nodes, rejects duplicate keys and emits deterministic sorted compact JSON.

## Re-evaluation triggers

Review only with measured customer inputs, infrastructure memory/latency budgets and parser-specific threat analysis.
