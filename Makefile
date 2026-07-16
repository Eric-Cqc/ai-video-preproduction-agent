SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

NODE_RUNNER := ./scripts/run-with-node.sh
UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
UV_RUN := UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --frozen --offline
PYTHONPATH := $(CURDIR):$(CURDIR)/packages/contracts/python:$(CURDIR)/packages/model-registry:$(PYTHONPATH)
DATABASE_URL ?= postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_local
TEST_DATABASE_URL ?= postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test
DB_COMPOSE := docker compose --project-name ai-video-preproduction-agent --file infra/docker/compose.postgres.yml
RC_API_PORT ?= 18000
RC_WEB_PORT ?= 13000

-include .env
export

.PHONY: setup dev-web dev-api dev-worker dev db-up db-down db-status db-upgrade db-downgrade db-current db-check db-reset-test test-domain test-persistence test-integration format format-check lint typecheck test contract-check build check rc-up rc-seed rc-smoke rc-check rc-down demo-smoke

setup:
	$(NODE_RUNNER) npm ci --registry=https://registry.npmjs.org/ --no-audit --no-fund
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --locked --index-url https://pypi.org/simple

dev-web:
	$(NODE_RUNNER) npm run dev:web

dev-api:
	$(UV_RUN) uvicorn services.api.app.main:app --host $(or $(API_HOST),127.0.0.1) --port $(or $(API_PORT),8000)

dev-worker:
	$(UV_RUN) python -m services.worker.app --self-check

dev:
	@set -e; \
	$(NODE_RUNNER) npm run dev:web & web_pid=$$!; \
	$(UV_RUN) uvicorn services.api.app.main:app --host $(or $(API_HOST),127.0.0.1) --port $(or $(API_PORT),8000) & api_pid=$$!; \
	trap 'kill $$web_pid $$api_pid 2>/dev/null || true' INT TERM EXIT; \
	$(UV_RUN) python -m services.worker.app --self-check; \
	wait

db-up:
	$(DB_COMPOSE) up --detach --wait postgres

db-down:
	$(DB_COMPOSE) down

db-status:
	$(DB_COMPOSE) ps

db-upgrade:
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic upgrade head

db-downgrade:
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic downgrade -1

db-current:
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic current --check-heads

db-check:
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic current --check-heads
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic check

db-reset-test:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) python -m infra.scripts.reset_test_database

test-domain:
	$(UV_RUN) pytest services/api/tests/domain

test-persistence:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) pytest services/api/tests/test_persistence.py services/api/tests/test_migrations.py services/api/tests/test_tenant_api.py services/api/tests/test_brief_api.py

test-integration:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) pytest tests/integration services/api/tests/test_tenant_api.py

format:
	$(NODE_RUNNER) npm run format
	$(UV_RUN) ruff format .
	$(UV_RUN) ruff check --fix .

format-check:
	$(NODE_RUNNER) npm run format:check
	$(UV_RUN) ruff format --check .

lint:
	$(NODE_RUNNER) npm run lint
	$(UV_RUN) ruff check .

typecheck:
	$(NODE_RUNNER) npm run typecheck
	$(UV_RUN) mypy

test:
	$(NODE_RUNNER) npm run test
	$(UV_RUN) pytest

contract-check:
	$(NODE_RUNNER) npm --workspace @foundation/contracts run test
	$(UV_RUN) pytest packages/contracts/python/tests tests/integration/test_api_contract.py

build:
	$(NODE_RUNNER) npm run build
	$(UV_RUN) python -m compileall -q services packages/contracts/python packages/model-registry

check: db-check format-check lint typecheck test contract-check build

rc-up: db-up db-upgrade
	API_BASE_URL=http://127.0.0.1:$(RC_API_PORT) $(MAKE) build
	@mkdir -p .local/rc; \
	if ! test -f .local/rc/api.pid || ! kill -0 $$(cat .local/rc/api.pid) 2>/dev/null; then \
	  $(UV_RUN) uvicorn services.api.app.main:app --host 127.0.0.1 --port $(RC_API_PORT) >.local/rc/api.log 2>&1 & echo $$! >.local/rc/api.pid; \
	fi; \
	if ! test -f .local/rc/web.pid || ! kill -0 $$(cat .local/rc/web.pid) 2>/dev/null; then \
	  WEB_PORT=$(RC_WEB_PORT) $(NODE_RUNNER) npm --workspace @foundation/web run start >.local/rc/web.log 2>&1 & echo $$! >.local/rc/web.pid; \
	fi; \
	for attempt in $$(seq 1 30); do curl --fail --silent http://127.0.0.1:$(RC_API_PORT)/api/v1/health | grep -q '"service":"foundation-api"' && curl --fail --silent http://127.0.0.1:$(RC_WEB_PORT) >/dev/null && exit 0; sleep 1; done; \
	exit 1

rc-seed:
	APP_ENVIRONMENT=local API_BASE_URL=http://127.0.0.1:$(RC_API_PORT) $(UV_RUN) python -m infra.scripts.rc_seed

rc-smoke:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) pytest -q services/api/tests/test_rc_golden_path.py

demo-smoke: rc-smoke

rc-check: db-current rc-smoke
	@curl --fail --silent http://127.0.0.1:$(RC_API_PORT)/api/v1/health | grep -q '"service":"foundation-api"'
	@curl --fail --silent http://127.0.0.1:$(RC_WEB_PORT) >/dev/null
	@test -w .local/source-objects || mkdir -p .local/source-objects

rc-down:
	@for service in api web; do if test -f .local/rc/$$service.pid; then kill $$(cat .local/rc/$$service.pid) 2>/dev/null || true; rm -f .local/rc/$$service.pid; fi; done
	$(MAKE) db-down
