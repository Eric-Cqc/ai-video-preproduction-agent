# ADR-055: Script-to-shot traceability

Status: Accepted for Stage 12

Application and database lineage pin ScriptVersion, selected concept and BriefVersion. Cross-project parent references are rejected through composite tenant/project foreign keys and scoped queries.

Storyboard generation requires one scene per Script scene and Shot Plan generation
requires every Storyboard scene to be covered while preserving source scene order.
