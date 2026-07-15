# Optional local PostgreSQL

`compose.postgres.yml` provides only PostgreSQL 17 for local development and tests. Application containers are intentionally absent. Native PostgreSQL remains supported through the same `DATABASE_URL` commands, so Docker is not the only workflow.

The Compose project, network, and volume are repository-scoped. `make db-down` stops this service without deleting its named volume; no command touches resources owned by another project.
