# Local release candidate quickstart

Prerequisites are the repository-pinned Node/Python environments, Docker and `curl`. Copy
`.env.example` to `.env` only for local overrides; never add credentials. Run `make rc-up`, then
`make rc-seed`. Open `http://127.0.0.1:13000`, enter the actor, organization and workspace IDs
from `.local/rc/context.json`, create a Project, and select the canonical Structured Brief v1 JSON
fixture. The Production Desk performs the persisted Golden Path and offers the server-generated
ZIP download. Run `make rc-smoke` and `make rc-check` for independent verification. Restart with
`make rc-down` followed by `make rc-up`; persistent Docker and local object data are retained.
Shut down with `make rc-down`. If readiness fails, inspect ignored `.local/rc/*.log`, confirm ports
18000/13000 are free, and rerun `make rc-up`.
