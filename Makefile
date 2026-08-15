SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

NODE_RUNNER := ./scripts/run-with-node.sh
UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
UV_RUN := UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --frozen --offline
PYTHONPATH := $(CURDIR):$(CURDIR)/packages/contracts/python:$(CURDIR)/packages/model-registry:$(PYTHONPATH)
DATABASE_URL ?= postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_local
TEST_DATABASE_URL ?= postgresql+psycopg://foundation:foundation@127.0.0.1:54329/foundation_test
DB_COMPOSE := docker compose --project-name ai-video-preproduction-agent --file infra/docker/compose.postgres.yml
HOSTED_COMPOSE := docker compose --env-file .env.hosted --file infra/docker/compose.hosted.yml
RC_API_PORT ?= 18000
RC_WEB_PORT ?= 13000
RC_API_BASE_URL ?= http://127.0.0.1:$(RC_API_PORT)
RC_WEB_BASE_URL ?= http://127.0.0.1:$(RC_WEB_PORT)
RC_STORAGE_ROOT ?= $(CURDIR)/.local/rc/source-objects
RC_CHECK_API_PORT ?= 18001
RC_CHECK_WEB_PORT ?= 13001
RC_CHECK_API_BASE_URL ?= http://127.0.0.1:$(RC_CHECK_API_PORT)
RC_CHECK_WEB_BASE_URL ?= http://127.0.0.1:$(RC_CHECK_WEB_PORT)
RC_CHECK_STORAGE_ROOT ?= $(CURDIR)/.local/rc/check-source-objects

-include .env
export

.PHONY: setup dev-web dev-api dev-worker dev db-up db-down db-status db-upgrade db-upgrade-test db-downgrade db-current db-current-test db-check db-reset-test test-domain test-persistence test-integration format format-check lint typecheck test test-web contract-check build check rc-up rc-seed rc-smoke rc-golden-path-test rc-check rc-down demo-smoke provider-live-smoke hosted-build hosted-up hosted-bootstrap hosted-smoke hosted-logs hosted-down

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

db-upgrade-test:
	DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) alembic upgrade head

db-downgrade:
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic downgrade -1

db-current:
	DATABASE_URL=$(DATABASE_URL) $(UV_RUN) alembic current --check-heads

db-current-test:
	DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) alembic current --check-heads

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

test: db-upgrade-test
	$(NODE_RUNNER) npm run test
	$(UV_RUN) pytest

test-web:
	$(NODE_RUNNER) npm --workspace @foundation/web run test

contract-check:
	$(NODE_RUNNER) npm --workspace @foundation/contracts run test
	$(UV_RUN) pytest packages/contracts/python/tests tests/integration/test_api_contract.py

build:
	$(NODE_RUNNER) npm run build
	$(UV_RUN) python -m compileall -q services packages/contracts/python packages/model-registry

check: db-check format-check lint typecheck test contract-check build

rc-up: db-up db-upgrade db-upgrade-test db-current db-current-test
	@set -euo pipefail; \
	rc_dir="$(CURDIR)/.local/rc"; \
	api_pid_file="$$rc_dir/api.pid"; \
	web_pid_file="$$rc_dir/web.pid"; \
	api_pid=""; web_pid=""; started_api=0; started_web=0; \
	stop_pid() { \
	  pid="$$1"; \
	  if kill -0 "$$pid" 2>/dev/null; then kill "$$pid" 2>/dev/null || true; fi; \
	  for attempt in $$(seq 1 50); do \
	    if ! kill -0 "$$pid" 2>/dev/null; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  kill -KILL "$$pid" 2>/dev/null || true; \
	}; \
	cleanup() { \
	  status="$$?"; \
	  trap - EXIT INT TERM; \
	  if [ "$$status" -ne 0 ]; then \
	    if [ "$$started_api" -eq 1 ] && [ -n "$$api_pid" ]; then stop_pid "$$api_pid"; rm -f "$$api_pid_file"; fi; \
	    if [ "$$started_web" -eq 1 ] && [ -n "$$web_pid" ]; then stop_pid "$$web_pid"; rm -f "$$web_pid_file"; fi; \
	  fi; \
	  exit "$$status"; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	mkdir -p "$$rc_dir" "$(RC_STORAGE_ROOT)"; \
	API_BASE_URL="$(RC_API_BASE_URL)" PUBLIC_API_BASE_URL="$(RC_API_BASE_URL)" $(MAKE) build; \
	if test -f "$$api_pid_file" && kill -0 "$$(cat "$$api_pid_file")" 2>/dev/null; then \
	  api_pid="$$(cat "$$api_pid_file")"; \
	else \
	  rm -f "$$api_pid_file"; \
	  nohup env \
	    DATABASE_URL="$(DATABASE_URL)" \
	    APP_ENVIRONMENT=local \
	    API_HOST=127.0.0.1 \
	    API_PORT="$(RC_API_PORT)" \
	    API_ALLOWED_CORS_ORIGINS="http://127.0.0.1:$(RC_WEB_PORT)" \
	    SOURCE_OBJECT_STORAGE_ADAPTER=local_filesystem_v1 \
	    SOURCE_OBJECT_STORAGE_ROOT="$(RC_STORAGE_ROOT)" \
	    MODEL_PROVIDER=deterministic_offline \
	    $(UV_RUN) uvicorn services.api.app.main:app --host 127.0.0.1 --port "$(RC_API_PORT)" \
	    >"$$rc_dir/api.log" 2>&1 & \
	  api_pid="$$!"; started_api=1; echo "$$api_pid" >"$$api_pid_file"; \
	fi; \
	if test -f "$$web_pid_file" && kill -0 "$$(cat "$$web_pid_file")" 2>/dev/null; then \
	  web_pid="$$(cat "$$web_pid_file")"; \
	else \
	  rm -f "$$web_pid_file"; \
	  nohup env \
	    APP_ENVIRONMENT=local \
	    API_BASE_URL="$(RC_API_BASE_URL)" \
	    PUBLIC_API_BASE_URL="$(RC_API_BASE_URL)" \
	    WEB_HOST=127.0.0.1 \
	    WEB_PORT="$(RC_WEB_PORT)" \
	    $(NODE_RUNNER) npm --workspace @foundation/web run start \
	    >"$$rc_dir/web.log" 2>&1 & \
	  web_pid="$$!"; started_web=1; echo "$$web_pid" >"$$web_pid_file"; \
	fi; \
	ready=0; \
	for attempt in $$(seq 1 60); do \
	  if curl --fail --silent "$(RC_API_BASE_URL)/api/v1/health" | grep -q '"service":"foundation-api"' && curl --fail --silent "$(RC_WEB_BASE_URL)" >/dev/null; then \
	    ready=1; break; \
	  fi; \
	  sleep 1; \
	done; \
	if [ "$$ready" -ne 1 ]; then echo "RC readiness failed; inspect $$rc_dir/api.log and $$rc_dir/web.log" >&2; exit 1; fi; \
	trap - EXIT INT TERM

rc-seed:
	APP_ENVIRONMENT=local API_BASE_URL=http://127.0.0.1:$(RC_API_PORT) $(UV_RUN) python -m infra.scripts.rc_seed

rc-golden-path-test:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV_RUN) pytest -q services/api/tests/test_rc_golden_path.py

rc-smoke:
	RC_API_BASE_URL="$(RC_API_BASE_URL)" RC_WEB_BASE_URL="$(RC_WEB_BASE_URL)" $(UV_RUN) python infra/scripts/rc_socket_smoke.py

demo-smoke: rc-smoke

provider-live-smoke:
	$(UV_RUN) python -m infra.scripts.provider_live_smoke

hosted-build:
	$(HOSTED_COMPOSE) build

hosted-up:
	$(HOSTED_COMPOSE) up --detach --wait

hosted-bootstrap:
	$(HOSTED_COMPOSE) exec api alembic upgrade head
	$(HOSTED_COMPOSE) exec api python -m infra.scripts.hosted_bootstrap

hosted-smoke:
	$(HOSTED_COMPOSE) exec api python -m infra.scripts.hosted_smoke

hosted-logs:
	$(HOSTED_COMPOSE) logs --follow --tail=100

hosted-down:
	$(HOSTED_COMPOSE) down

rc-check: db-up db-upgrade-test db-current-test
	@set -euo pipefail; \
	rc_dir="$(CURDIR)/.local/rc"; \
	api_pid_file="$$rc_dir/check-api.pid"; \
	web_pid_file="$$rc_dir/check-web.pid"; \
	api_pid=""; web_pid=""; \
	stop_pid() { \
	  pid="$$1"; \
	  if kill -0 "$$pid" 2>/dev/null; then kill "$$pid" 2>/dev/null || true; fi; \
	  for attempt in $$(seq 1 50); do \
	    if ! kill -0 "$$pid" 2>/dev/null; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  kill -KILL "$$pid" 2>/dev/null || true; \
	}; \
	cleanup() { \
	  status="$$?"; \
	  trap - EXIT INT TERM; \
	  if [ -n "$$api_pid" ]; then stop_pid "$$api_pid"; fi; \
	  if [ -n "$$web_pid" ]; then stop_pid "$$web_pid"; fi; \
	  rm -f "$$api_pid_file" "$$web_pid_file"; \
	  exit "$$status"; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	mkdir -p "$$rc_dir" "$(RC_CHECK_STORAGE_ROOT)"; \
	rm -f "$$api_pid_file" "$$web_pid_file"; \
	API_BASE_URL="$(RC_CHECK_API_BASE_URL)" PUBLIC_API_BASE_URL="$(RC_CHECK_API_BASE_URL)" $(MAKE) build; \
	nohup env \
	  DATABASE_URL="$(TEST_DATABASE_URL)" \
	  APP_ENVIRONMENT=local \
	  API_HOST=127.0.0.1 \
	  API_PORT="$(RC_CHECK_API_PORT)" \
	  API_ALLOWED_CORS_ORIGINS="http://127.0.0.1:$(RC_CHECK_WEB_PORT)" \
	  SOURCE_OBJECT_STORAGE_ADAPTER=local_filesystem_v1 \
	  SOURCE_OBJECT_STORAGE_ROOT="$(RC_CHECK_STORAGE_ROOT)" \
	  MODEL_PROVIDER=deterministic_offline \
	  $(UV_RUN) uvicorn services.api.app.main:app --host 127.0.0.1 --port "$(RC_CHECK_API_PORT)" \
	  >"$$rc_dir/check-api.log" 2>&1 & \
	api_pid="$$!"; echo "$$api_pid" >"$$api_pid_file"; \
	nohup env \
	  APP_ENVIRONMENT=local \
	  API_BASE_URL="$(RC_CHECK_API_BASE_URL)" \
	  PUBLIC_API_BASE_URL="$(RC_CHECK_API_BASE_URL)" \
	  WEB_HOST=127.0.0.1 \
	  WEB_PORT="$(RC_CHECK_WEB_PORT)" \
	  $(NODE_RUNNER) npm --workspace @foundation/web run start \
	  >"$$rc_dir/check-web.log" 2>&1 & \
	web_pid="$$!"; echo "$$web_pid" >"$$web_pid_file"; \
	ready=0; \
	for attempt in $$(seq 1 60); do \
	  if curl --fail --silent "$(RC_CHECK_API_BASE_URL)/api/v1/health" | grep -q '"service":"foundation-api"' && curl --fail --silent "$(RC_CHECK_WEB_BASE_URL)" >/dev/null; then \
	    ready=1; break; \
	  fi; \
	  sleep 1; \
	done; \
	if [ "$$ready" -ne 1 ]; then echo "RC check readiness failed; inspect $$rc_dir/check-api.log and $$rc_dir/check-web.log" >&2; exit 1; fi; \
	RC_API_BASE_URL="$(RC_CHECK_API_BASE_URL)" RC_WEB_BASE_URL="$(RC_CHECK_WEB_BASE_URL)" $(UV_RUN) python infra/scripts/rc_socket_smoke.py

rc-down:
	@set -euo pipefail; \
	rc_dir="$(CURDIR)/.local/rc"; \
	stop_pid() { \
	  pid="$$1"; \
	  if kill -0 "$$pid" 2>/dev/null; then kill "$$pid" 2>/dev/null || true; fi; \
	  for attempt in $$(seq 1 50); do \
	    if ! kill -0 "$$pid" 2>/dev/null; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  kill -KILL "$$pid" 2>/dev/null || true; \
	}; \
	for service in api web; do \
	  pid_file="$$rc_dir/$$service.pid"; \
	  if test -s "$$pid_file"; then stop_pid "$$(cat "$$pid_file")"; fi; \
	  rm -f "$$pid_file"; \
	done
	$(MAKE) db-down
