# ADR-037: Immutable document extraction artifact

Status: Accepted for Stage 8

## Decision

Persist an immutable tenant/Project/SourceAssetVersion-scoped DocumentExtraction containing bounded canonical structured output, parser identifier/version, verified source checksum, options digest, extraction checksum, counts and warnings. Parser upgrades or option changes create new records; no update endpoint exists.

## Re-evaluation triggers

Review database JSONB storage when outputs exceed the bounded limit, retention differs from source objects, or a production artifact store is approved.
