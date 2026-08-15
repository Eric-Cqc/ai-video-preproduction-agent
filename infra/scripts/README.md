# Infrastructure scripts

`reset_test_database.py` is the only destructive helper. It refuses any database whose name does not end in `_test`, truncates the complete tenant test-table set (including Stage 13 review, revision, package and operation rows), and is exposed as the explicit `make db-reset-test` command.

`rc_socket_smoke.py` is the non-destructive socket-level Local RC verifier. It talks only to the
running API and Web bases from `RC_API_BASE_URL` and `RC_WEB_BASE_URL` (defaulting to ports
`18000/13000`), bootstraps unique tenants per run, walks the human-gated production path through
ZIP export, and checks replay/conflict, authorization, tenant isolation, manifest, checksum, and
ZIP membership. It never prints source text, prompts, secrets, or raw response bodies. Invoke it
through `make rc-smoke`; `make rc-check` supplies isolated `18001/13001` bases.

There are no cloud or deployment scripts. Normal developer commands remain in the root Makefile.
