# ADR-047: Candidate review audit and exposure

Status: Accepted for Stage 10

Candidate content is available only through scoped review reads. Audit stores identifiers, action, digests and bounded counts only; it never stores raw provider output, prompts, source text or full accepted content.

Owner/admin/member may accept or reject; viewer may read but receives 403 for a mutation. Inaccessible and nonexistent tenant/Workspace/Project/run combinations share one opaque 404 representation.
