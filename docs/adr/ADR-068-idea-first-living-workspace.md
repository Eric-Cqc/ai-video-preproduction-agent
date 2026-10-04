# ADR-068 — Idea-first living artifact workspace

Status: implemented for isolated development review (2026-10-02).

## Context

[Stage23](../development/plans/stage-23-frontend-redesign-plan.md) fixes the SaaS visual direction and retains human gates. The public baseline includes partial stage/component/token work. This additive integration combines it with the first-class IdeaIntake implementation on an independent review branch.

## Decision

Retain the modular monolith, current HTTP routes, canonical schemas and immutable planning versions. Integrate the existing first-class IdeaIntake as an additive, tenant-scoped entry point. Confirmation ends at Brief: it never chooses a Concept or approves a bundle. Compose its client separately so existing planning contracts remain stable. Add a scoped, read-only Concept selection endpoint so hydration cannot create a choice from a browser handle. Show only server-read artifacts in a living artifact directory. Browser storage keeps scoped IDs and operation handles, never authoritative approval state or raw idea content.

Architecture options considered: (1) existing stage orchestration plus a composed intake boundary and artifact directory (chosen: smallest verifiable integration); (2) an event-sourced universal editor (deferred: new persistence/schema complexity without evidence); (3) a separate showcase/mock product (rejected: would bypass the existing application and human gates).

Intake duration validation now matches canonical Structured Brief v1 (15–60 seconds), preventing a draft that cannot be confirmed. The existing intake migration conflicts with a historical Stage20 revision ID. Add a fresh migration after the verified Stage22 head, retain all preceding audit actions, and refuse data-bearing downgrade. Preserve the already-applied intake migration's original bounds; subsequent migrations align duration and the organization FK with ORM metadata without rewriting rows. Out-of-range existing drafts block the duration upgrade and require human review. Authorize before structuring an idea. Script template 1.1 receives both the selected Concept and pinned canonical Brief, so offline templates preserve requested duration and CTA rather than silently emitting a generic ten-second script. The deterministic provider is versioned as fixture-workflow-v2 and emits three declared template directions. Default provider remains deterministic offline; its inferred fields are explicitly assumptions and editable.

## Replaceable assumptions / review triggers

Same-browser planning resume remains the supported baseline. Intake is recoverable through a server list even without browser handles. Full cross-device discovery of every planning lineage is deferred until server enumeration contracts exist. A universal editor or state-machine dependency requires demonstrated complexity beyond the existing pure workspace model. No new frontend runtime dependency, authentication system, provider implementation, deployment, image/video generation or publishing capability is introduced. Idea structuring uses the existing configured workflow provider. The deterministic provider works offline; selecting the existing DeepSeek provider sends the submitted idea text to that provider. Browser mode labels describe access mode and do not establish whether model processing is offline.

See [Foundation](../../FOUNDATION.md), [product scope](../product/product-scope.md), ADR-043 and ADR-058 for human-review boundaries.
