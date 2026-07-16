# ADR-057: Duration and continuity validation

Status: Accepted for Stage 12

Storyboard and shot duration/sequence/parent validation is explicit and rejects invalid output. The system does not silently repair provider candidates.

Stage 12 applies a one-second bounded duration tolerance, checks scene and total
duration against the pinned Script, and rejects continuity references to future or
nonexistent shots before any completed artifact is persisted.
