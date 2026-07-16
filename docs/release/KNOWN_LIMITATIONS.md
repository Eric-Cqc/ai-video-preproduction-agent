# Known limitations

This is a local release candidate with deterministic offline providers, canonical JSON input and
local filesystem object storage. It has no production identity provider, remote AI, PDF/DOCX/XLSX
rich parsing beyond existing adapters, cloud storage, background jobs, queues, image/video
generation, media rendering or production deployment. The installed Starlette TestClient emits a
dependency-owned deprecation warning; resolving it requires a dependency/lockfile change and is
therefore deferred.
