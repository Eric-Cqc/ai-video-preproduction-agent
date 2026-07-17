# Local RC release checklist

- `make rc-up`, `make rc-seed`, `make rc-smoke`, and `make rc-check` pass.
- `make check` passes with migration head `a1b2c3d4e5f6` and no metadata drift.
- ZIP manifest and checksum pass; no export, storage object, log, screenshot or database is staged.
- Only deterministic offline providers are enabled; no SDK, secret, network provider or tool use exists.
- `make rc-down` completes without deleting persistent data.
