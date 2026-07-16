# Local product hardening

The web workspace sends no credentials and keeps only its temporary local tenant context in
browser storage. Mutation idempotency keys are generated per user action; safe reads alone may
retry transient gateway errors. Every request has an abort boundary and user-facing error states
avoid internal digest, SQL, provider and constraint details.

The web response policy disables framing, MIME sniffing and unused browser permissions while
keeping the application offline. Existing API correlation IDs, bounded request handling,
tenant-scoped opaque 404s and audit boundaries remain the server-side reliability controls.
