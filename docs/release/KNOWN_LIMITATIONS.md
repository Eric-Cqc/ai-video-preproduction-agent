# Known limitations

## Local RC

The Local RC uses deterministic offline providers, canonical JSON input, and the checked-in
`local_filesystem_v1` object adapter. It has no cloud object storage, production identity provider,
remote AI by default, PDF/DOCX/XLSX rich parsing beyond existing adapters, background jobs, queues,
image/video generation, media rendering, or publishing. The installed Starlette TestClient emits a
dependency-owned deprecation warning; resolving it requires a dependency/lockfile change and is
therefore deferred.

## Hosted pilot truth

Hosted pilot mechanics exist: the narrowly approved ADR-064 server-side DeepSeek adapter, the
explicit private pilot access gate, and the local-operable Docker Compose topology are implemented.
ADR-066 keeps that pilot single-tenant, private, and bounded; its application files are
volume-backed, not cloud object storage.

Hosted acceptance is **not done**. The ADR-064 privacy, retention, cost, and availability review,
plus live end-to-end chain validation, remain outside this stage. CI, ordinary tests, and the Local
RC remain fully deterministic and offline.

## Bounded residuals and access limits

- F-09: storage finalization can precede the database commit. This is the accepted ADR-034
  controlled residual; reconciliation is not added in this stage and the post-stage owner is next
  stage planning.
- The Production Desk always submits candidate acceptance with `brief_id: null`, so accepted
  candidates create Brief version 1 of a new Brief lineage; accepting into an existing Brief
  lineage is API-only in this stage.
- Local/test/ci request-context headers are spoofable development context, not authentication.
- The hosted pilot is single-tenant and does not provide production multi-tenant identity,
  collaboration, or authorization.
- Provider live validation is explicit, external, cost-bearing work and is excluded from
  `make check`.
