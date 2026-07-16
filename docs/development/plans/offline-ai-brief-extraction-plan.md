# Offline AI Brief extraction foundation plan

Status: completed (Stage 9 safe foundation)

## Scope and dependency decision

Create a model-independent provider port, versioned instruction template, immutable run/attempt records, deterministic fake provider and offline evaluation fixtures. No real provider, SDK, credential, network call, API endpoint or automatic Brief mutation is allowed. Existing jsonschema/Structured Brief contract is sufficient; dependencies and lockfiles remain unchanged.

## Frozen decisions

- Model output is an untrusted candidate, never an approved Brief or in-place BriefVersion update.
- The prompt template is versioned in code and instructs JSON-only output, no tools, no URL fetch, no code execution and treatment of extracted text as data.
- Provider/model identifiers, template version, input extraction checksum, output digest and immutable attempt classification are persisted. Full prompt, extraction text and raw provider output are not persisted or audited.
- Output must be raw JSON, bounded to 256 KiB, and pass the canonical Structured Brief v1 JSON Schema. Markdown fences, extra fields, wrong schema version and malformed JSON fail.
- Candidate runs end in `human_review_required`; failures remain failed attempts. There is no path in this stage from candidate to BriefVersion.

## Threat model

Treat prompt injection in documents as inert data; prohibit provider tools and external actions; bound input to 128,000 characters and output to 256 KiB; classify refusal, timeout, provider error, malformed JSON and schema-invalid output; exclude full content/prompts/raw output/secrets from logs and audit; scope every read/write by tenant and Project.

## Milestones

- A — plan, ADR-040 through ADR-043, dependency/threat decision.
- B — immutable run/attempt domain, migration/metadata and constraints.
- C — scoped repositories/UoW and atomic run/attempt/audit.
- D — provider port, deterministic fake, service, offline golden/error tests.
- E — docs, migration/full gates, staged review and independent report.

## Replaceable assumptions and triggers

The fake provider and code-owned template are test foundations. Review before any real provider, SDK, credential, network access, retry policy, cost/token accounting, API exposure, candidate acceptance workflow or model comparison is introduced.
