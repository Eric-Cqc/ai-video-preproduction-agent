# ADR-053: Storyboard versioning

Status: Accepted for Stage 12

StoryboardVersion is immutable and pins BriefVersion, selected concept, ScriptVersion and generation provenance. It contains no generated image.

Stage 12 implements this with a tenant-scoped composite lineage foreign key and
an immutable version repository. Generation uses only the deterministic offline
fixture provider; replay and CAS state live in `visual_planning_operations`.
