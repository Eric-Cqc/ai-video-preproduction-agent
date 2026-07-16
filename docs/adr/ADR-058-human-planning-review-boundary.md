# ADR-058 — Human Planning Review Boundary

Status: Accepted for Stage 13

Stage 13 introduces an explicit, tenant-scoped human review over immutable
ScriptVersion, StoryboardVersion and ShotPlanVersion snapshots. Approval,
rejection and revision requests are recorded as immutable review facts; no
review mutates an artifact in place. A review never invokes a real provider,
network, renderer or background job.

The review is the authorization boundary for delivery. A delivery package may
reference only the exact approved planning bundle that was reviewed.
