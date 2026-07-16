# Provider conformance

Only deterministic offline fixture providers are registered. The shared capability boundary records provider/model IDs, capability, schema versions, bounded input/output sizes and explicit failure classes. Strict JSON, wrapper rejection, malformed/schema/semantic failure modes and refusal/timeout/error paths remain exercised by existing provider tests; no automatic repair is permitted.
