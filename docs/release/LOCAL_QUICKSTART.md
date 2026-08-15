# Local release candidate quickstart

## Prerequisites

The supported Local RC path requires:

- GNU Make and Bash.
- The pinned Node.js version in `.node-version`, with `fnm` available when the repository
  wrapper needs to select it. JavaScript commands run through `./scripts/run-with-node.sh`.
- Python 3.13 and the repository-compatible `uv` release.
- A running Docker daemon for the repository-scoped PostgreSQL 17 Compose service.
- `curl` for readiness checks.

No cloud account, Provider credential, or manual database setup is required for the deterministic
Local RC.

## From a fresh checkout

Run setup first:

```sh
make setup
```

Then start and seed the RC:

```sh
make rc-up
make rc-seed
```

`rc-up` starts PostgreSQL, migrates both `foundation_local` and `foundation_test` to the Alembic
head, verifies both heads, builds the Web app, and starts the API on `18000` and Web on `13000`.
There is no manual database migration step anymore. The RC uses repository-local filesystem
storage under `.local/rc/source-objects`.

Open `http://127.0.0.1:13000`. The context written to `.local/rc/context.json` supplies the
temporary actor, Organization, and Workspace IDs. In the Production Desk, complete the real
human-gated path:

1. Create or select a Project and upload the canonical Structured Brief v1 source.
2. Review the extracted Brief candidate and explicitly Accept or Reject it.
3. Compare the three concept candidates and explicitly select one.
4. Run Script, Storyboard, and Shot Plan as separate, visible actions.
5. Review the complete planning bundle and explicitly Approve it or request changes.
6. Open Delivery, create the package, export the ZIP, and verify its manifest and checksum.

## RC verification commands

```sh
make rc-golden-path-test  # in-process API golden-path regression
make rc-smoke             # socket-level smoke: full API workflow + Web health/render check
make rc-check             # isolated 18001/13001 socket cycle on foundation_test
make demo-smoke           # alias of rc-smoke
make rc-down
```

`rc-smoke` and `rc-check` create unique tenant data per run and never print source text,
prompts, or secrets. Persistent Docker database data and local RC object data are retained after
`make rc-down`. If readiness fails, inspect the ignored `.local/rc/api.log`, `.local/rc/web.log`,
`.local/rc/check-api.log`, or `.local/rc/check-web.log`, confirm ports `18000/13000` and
`18001/13001` are free, and rerun the relevant command.
