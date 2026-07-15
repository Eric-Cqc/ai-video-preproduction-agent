# PostgreSQL migrations

Alembic owns the committed PostgreSQL schema history for the tenant persistence foundation. Run migrations through the root Makefile; do not edit an already-applied migration to change history. Revision `b2a7c9d1e4f0` adds controlled Brief ingestion with composite ownership, Project-scoped idempotency and internal `reserved → accepted` checks. Revisions `c4f1d2a9b8e7` through `f1a2b3c4d5e6` add metadata-only SourceAsset identities, immutable versions, scoped operation reservations and ordered Brief-ingestion attachments; they do not create file storage.

New revisions require an explicit message and review of generated constraints, indexes, upgrade, and downgrade operations. PostgreSQL—not SQLite—is the migration contract. See ADR-012.
