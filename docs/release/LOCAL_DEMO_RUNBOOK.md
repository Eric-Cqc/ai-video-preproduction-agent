# Local demo runbook

Use `make rc-up`, `make rc-seed`, and the context written under the ignored `.local/rc` directory.
The supported input is canonical Structured Brief v1 JSON. Demonstrate the visible progress
messages through upload, parse, human Brief acceptance, Concepts, Script, Storyboard, Shot Plan,
bundle approval, Delivery and ZIP download. `make rc-smoke` repeats the same business sequence
through HTTP against real services, PostgreSQL and local storage and verifies replay, conflict,
lineage, ZIP manifest and checksum. It never calls a remote provider.
