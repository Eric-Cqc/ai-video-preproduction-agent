# ADR-054: Shot identity and ordering

Status: Accepted for Stage 12

ShotPlanVersion is immutable. Shot numbering is contiguous and each shot is scoped to a storyboard scene and source script scene in the same Project.

Each shot also carries an explicit stable `shot_id`; duplicate IDs, duplicate or
non-consecutive orders, unknown scenes and missing scene coverage are rejected.
