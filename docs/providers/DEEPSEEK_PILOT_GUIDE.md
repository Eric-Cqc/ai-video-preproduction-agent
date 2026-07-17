# DeepSeek Hosted Pilot guide

Create an ignored local `.env` from `.env.example`. Keep `MODEL_PROVIDER=deterministic_offline`
for ordinary local work, tests and CI. To opt in locally, set only `MODEL_PROVIDER=deepseek` and
`DEEPSEEK_API_KEY`; the fixed endpoint, model, timeout and bounds are server configuration, never
browser or request fields. Return to deterministic mode by removing the key and selecting the
default mode.

The adapter sends bounded server-owned instructions and the minimum upstream structured artifact
content required by the capability. That content is delimited as untrusted data. It never persists
or audits the full prompt, raw request/response, reasoning, key, or source text. Existing artifact
lineage, schema/semantic validation, idempotency, CAS and rollback rules remain in force. Usage
metadata is bounded when supplied, but no new speculative persistence is added.

Retries are limited to two attempts for transport timeouts and selected 5xx/rate-limit responses;
authentication, refusal, malformed/schema/semantic-invalid and security failures do not retry.

`make provider-live-smoke` is deliberately excluded from CI and `make check`. It requires
`ALLOW_PROVIDER_LIVE_SMOKE=1`, `MODEL_PROVIDER=deepseek`, and an explicit local key, and can
incur API cost. It exercises one representative production capability, not the complete Golden
Path: DeepSeek authentication → JSON response → the production Structured Brief Schema → the
production Structured Brief semantic validation. The command uses only a fixed synthetic,
generic fictional reusable-notebook brief; it sends no customer content, uploads, URLs, or
browsing instructions. Validation is in memory only: it creates no application artifact,
database record, audit event, or storage object, and it displays neither the prompt nor the raw
response. Successful output is limited to provider/model, validation status, and bounded usage
metadata. Hosted deployment, authentication and cloud storage are not part of this pilot.
