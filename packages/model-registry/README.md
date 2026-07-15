# Model registry foundation

This package is a deliberately small Adapter boundary: a validated capability description, a protocol, and duplicate-safe registration. It has no Provider implementation, API client, credentials, Prompt, routing algorithm, or generation behavior.

Add a real Provider only after product authorization and an Adapter contract review under ADR-005. Provider-specific types must remain behind the adapter.
