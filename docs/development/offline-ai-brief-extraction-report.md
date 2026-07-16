# Offline AI Brief extraction foundation report

## Outcome

Stage 9 adds an offline-only safety foundation: a model-neutral port, deterministic fake provider, versioned server-owned instructions, strict canonical Structured Brief validation, and immutable tenant-scoped Run/Attempt records. It adds no API endpoint, real provider, SDK, credential, network call or automatic Brief mutation.

## Frozen behavior

- Source is an existing immutable DocumentExtraction and is rechecked by full tenant, Project, Asset and Version scope before persistence.
- Input is untrusted data. Instructions prohibit tools, URL fetch, code execution and external actions.
- Input is limited to 128,000 characters; output to 262,144 characters.
- Only raw finite JSON conforming to canonical Structured Brief v1 becomes a candidate.
- Success is `human_review_required`; failures classify malformed output, schema invalidity, refusal, timeout or provider error.
- Runs, attempts and bounded audit are one UoW transaction. Full prompt/input/raw output are not persisted or audited.
- No Brief, BriefVersion or RequirementIssue is created or changed.

## Replaceable assumptions and review triggers

The fake provider and code-owned instruction template are replaceable test foundations. Before any real model, SDK, credential, network call, retries, asynchronous execution, API exposure or candidate-acceptance workflow, add an ADR covering privacy, retention, threat model, cost, permissions and evaluation gates.

Related decisions: [ADR-040](../adr/ADR-040-model-provider-port-offline.md), [ADR-041](../adr/ADR-041-versioned-brief-extraction-instructions.md), [ADR-042](../adr/ADR-042-immutable-extraction-runs-and-attempts.md), and [ADR-043](../adr/ADR-043-human-review-candidate-boundary.md).
