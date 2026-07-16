# ADR-062 — Delivery Package and Safe Exports

Status: Accepted for Stage 13

A DeliveryPackageVersion stores a deterministic manifest pinned to the exact
approved ScriptVersion, StoryboardVersion and ShotPlanVersion content digests.
Exports are generated as canonical JSON, CSV, README and reproducible ZIP
bytes. ZIP timestamps and ordering are fixed. Export bytes are staged through
StoragePort, finalized under an opaque key, and compensated on database
failure; generated files are not committed to the repository.
