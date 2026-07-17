# Deterministic local end-to-end demo

The local walkthrough demonstrates the complete preproduction path without a real model,
network provider, media generation, rendering, background work, or committed export bytes.
Its fixed public fixture sequence is: approved Intake, Brief, Concept selection, Script,
Storyboard, Shot Plan, Review, and Delivery package. Every item is version 1 and the delivery
entry is terminal.

For a live local walkthrough, start the existing local API and web applications, enter a
non-secret local actor/organization/workspace context in Production Desk, create or select a
project, and follow the production rail. The API remains the source of truth; the fixture only
documents a repeatable teaching path and never writes to the database.

The Vitest check in `apps/web/tests/demo-workflow.test.ts` guards ordering, predecessor approval
and terminal delivery state. It is deliberately pure and deterministic, so it runs offline.
