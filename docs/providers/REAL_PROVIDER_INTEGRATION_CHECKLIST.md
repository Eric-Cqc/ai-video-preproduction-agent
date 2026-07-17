# Real provider integration checklist

Hosted Pilot Phase 1 implements the narrowly approved ADR-064 DeepSeek Adapter. It remains opt-in,
server-only, JSON-only, bounded and covered by offline mock transport tests. Live smoke requires an
explicit local key and is never part of CI or `make check`; hosted deployment, identity and cloud
storage remain unimplemented.
