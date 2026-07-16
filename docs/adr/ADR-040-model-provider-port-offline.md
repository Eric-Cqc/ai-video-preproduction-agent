# ADR-040: Offline model provider port

Status: Accepted for Stage 9 foundation

## Decision

Define a model-neutral ProviderPort and deterministic fixture-based fake implementation. No SDK, network, credential or real model is present. Provider outcomes are bounded success, refusal, timeout or error classifications; tool use and external actions are outside the contract.

## Re-evaluation triggers

Review with a separate threat/cost/privacy ADR before connecting any real provider.
