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
GRACE_HOURS ?= 24

-include .env
export

.PHONY: setup dev-web dev-api dev-worker dev db-up db-down db-status db-upgrade db-upgrade-test db-downgrade db-current db-current-test db-check db-reset-test test-domain test-persistence test-integration format format-check lint typecheck test test-web contract-check build check rc-up rc-seed rc-smoke rc-golden-path-test rc-check rc-down demo-smoke provider-live-smoke storage-sweep hosted-env-local hosted-build hosted-up hosted-bootstrap hosted-smoke hosted-logs hosted-backup hosted-down hosted-env-file

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

# RC ownership safety check: inspect `.owner` markers and use `make rc-down`; a live PID
# without a matching start-time/command marker must be warned about and left untouched.
rc-up: db-up db-upgrade db-upgrade-test db-current db-current-test
	@set -euo pipefail; \
	rc_dir="$(CURDIR)/.local/rc"; \
	api_pid_file="$$rc_dir/api.pid"; \
	web_pid_file="$$rc_dir/web.pid"; \
	api_owner_file="$$rc_dir/api.owner"; \
	web_owner_file="$$rc_dir/web.owner"; \
	api_pid=""; web_pid=""; started_api=0; started_web=0; \
	pid_is_live() { \
	  pid="$$1"; \
	  case "$$pid" in ''|*[!0-9]*) return 1;; esac; \
	  kill -0 "$$pid" 2>/dev/null; \
	}; \
	process_owned() { \
	  pid="$$1"; marker_file="$$2"; \
	  if ! pid_is_live "$$pid" || ! test -s "$$marker_file"; then return 1; fi; \
	  IFS='|' read -r marker_pid marker_start marker_service marker_port marker_pattern < "$$marker_file"; \
	  [ "$$marker_pid" = "$$pid" ] && [ -n "$$marker_start" ] && [ -n "$$marker_port" ] && [ -n "$$marker_pattern" ] || return 1; \
	  current_start="$$(ps -p "$$pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//; s/[[:space:]]*$$//' || true)"; \
	  current_command="$$(ps -p "$$pid" -o command= 2>/dev/null || true)"; \
	  [ "$$current_start" = "$$marker_start" ] || return 1; \
	  case "$$marker_service" in api|web) ;; *) return 1;; esac; \
	  case "$$current_command" in *"$$marker_pattern"*) ;; *) return 1;; esac; \
	}; \
	write_owner_marker() { \
	  pid="$$1"; service="$$2"; port="$$3"; pattern="$$4"; marker_file="$$5"; \
	  for attempt in $$(seq 1 20); do \
	    marker_start="$$(ps -p "$$pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//; s/[[:space:]]*$$//' || true)"; \
	    marker_command="$$(ps -p "$$pid" -o command= 2>/dev/null || true)"; \
	    if [ -n "$$marker_start" ] && case "$$marker_command" in *"$$pattern"*) true;; *) false;; esac; then \
	      printf '%s|%s|%s|%s|%s\n' "$$pid" "$$marker_start" "$$service" "$$port" "$$pattern" >"$$marker_file"; \
	      return 0; \
	    fi; \
	    sleep 0.1; \
	  done; \
	  return 1; \
	}; \
	stop_pid() { \
	  pid="$$1"; marker_file="$$2"; \
	  if ! pid_is_live "$$pid"; then return 0; fi; \
	  if ! process_owned "$$pid" "$$marker_file"; then echo "Refusing to stop live unowned RC PID $$pid" >&2; return 2; fi; \
	  kill "$$pid" 2>/dev/null || true; \
	  for attempt in $$(seq 1 50); do \
	    if ! pid_is_live "$$pid"; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  kill -KILL "$$pid" 2>/dev/null || true; \
	  for attempt in $$(seq 1 20); do \
	    if ! pid_is_live "$$pid"; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  echo "Owned RC PID $$pid did not exit after SIGKILL" >&2; return 1; \
	}; \
	cleanup() { \
	  status="$$?"; \
	  trap - EXIT INT TERM; \
	  if [ "$$status" -ne 0 ]; then \
	    if [ "$$started_api" -eq 1 ] && [ -n "$$api_pid" ] && stop_pid "$$api_pid" "$$api_owner_file"; then rm -f "$$api_pid_file" "$$api_owner_file"; fi; \
	    if [ "$$started_web" -eq 1 ] && [ -n "$$web_pid" ] && stop_pid "$$web_pid" "$$web_owner_file"; then rm -f "$$web_pid_file" "$$web_owner_file"; fi; \
	  fi; \
	  exit "$$status"; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	mkdir -p "$$rc_dir" "$(RC_STORAGE_ROOT)"; \
	API_BASE_URL="$(RC_API_BASE_URL)" PUBLIC_API_BASE_URL="$(RC_API_BASE_URL)" $(MAKE) build; \
	if test -s "$$api_pid_file" && pid_is_live "$$(cat "$$api_pid_file")"; then \
	  api_pid="$$(cat "$$api_pid_file")"; \
	  if ! process_owned "$$api_pid" "$$api_owner_file"; then echo "Refusing to reuse live unowned RC API PID $$api_pid" >&2; exit 1; fi; \
	else \
	  rm -f "$$api_pid_file" "$$api_owner_file"; \
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
	  if ! write_owner_marker "$$api_pid" api "$(RC_API_PORT)" "uvicorn services.api.app.main:app" "$$api_owner_file"; then echo "RC API ownership marker could not be established" >&2; exit 1; fi; \
	fi; \
	if test -s "$$web_pid_file" && pid_is_live "$$(cat "$$web_pid_file")"; then \
	  web_pid="$$(cat "$$web_pid_file")"; \
	  if ! process_owned "$$web_pid" "$$web_owner_file"; then echo "Refusing to reuse live unowned RC web PID $$web_pid" >&2; exit 1; fi; \
	else \
	  rm -f "$$web_pid_file" "$$web_owner_file"; \
	  nohup env \
	    APP_ENVIRONMENT=local \
	    API_BASE_URL="$(RC_API_BASE_URL)" \
	    PUBLIC_API_BASE_URL="$(RC_API_BASE_URL)" \
	    WEB_HOST=127.0.0.1 \
	    WEB_PORT="$(RC_WEB_PORT)" \
	    $(NODE_RUNNER) npm --workspace @foundation/web run start \
	    >"$$rc_dir/web.log" 2>&1 & \
	  web_pid="$$!"; started_web=1; echo "$$web_pid" >"$$web_pid_file"; \
	  if ! write_owner_marker "$$web_pid" web "$(RC_WEB_PORT)" "@foundation/web" "$$web_owner_file"; then echo "RC web ownership marker could not be established" >&2; exit 1; fi; \
	fi; \
	ready=0; \
	for attempt in $$(seq 1 60); do \
	  if curl --connect-timeout 2 --max-time 10 --fail --silent "$(RC_API_BASE_URL)/api/v1/health" | grep -q '"service":"foundation-api"' && curl --connect-timeout 2 --max-time 10 --fail --silent "$(RC_WEB_BASE_URL)" >/dev/null; then \
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

storage-sweep:
	$(UV_RUN) python -m infra.scripts.storage_sweep --grace-hours "$(GRACE_HOURS)" $(if $(filter 1,$(APPLY)),--apply,)

hosted-build:
	@test -f .env.hosted || { echo "Missing .env.hosted; run 'make hosted-env-local' for local validation." >&2; exit 1; }
	$(HOSTED_COMPOSE) build

hosted-up:
	@test -f .env.hosted || { echo "Missing .env.hosted; run 'make hosted-env-local' for local validation." >&2; exit 1; }
	$(HOSTED_COMPOSE) up --detach --wait

hosted-env-local:
	$(UV_RUN) python infra/scripts/make_local_hosted_env.py

hosted-env-file:
	@test -f .env.hosted || { echo "Missing .env.hosted; run 'make hosted-env-local' for local validation." >&2; exit 1; }

hosted-bootstrap: hosted-env-file
	$(HOSTED_COMPOSE) exec -T api alembic upgrade head
	$(HOSTED_COMPOSE) exec -T api python -m infra.scripts.hosted_bootstrap

hosted-smoke: hosted-env-file
	$(HOSTED_COMPOSE) exec -T \
		-e PILOT_BASE_URL=http://caddy:80 \
		-e HOSTED_SMOKE_CA_BUNDLE="$${HOSTED_SMOKE_CA_BUNDLE:-}" \
		-e HOSTED_SMOKE_INSECURE="$${HOSTED_SMOKE_INSECURE:-}" \
		api sh -c 'if { test "$${PILOT_DOMAIN}" = localhost || test "$${PILOT_DOMAIN}" = 127.0.0.1; } && test -z "$${HOSTED_SMOKE_CA_BUNDLE}" && test -f /var/lib/caddy-data/caddy/pki/authorities/local/root.crt; then export HOSTED_SMOKE_CA_BUNDLE=/var/lib/caddy-data/caddy/pki/authorities/local/root.crt; fi; exec python -m infra.scripts.hosted_proxy_smoke --assert-bootstrap'

hosted-logs: hosted-env-file
	$(HOSTED_COMPOSE) logs --follow --tail=100

hosted-backup: hosted-env-file
	@set -euo pipefail; \
	if [ -z "$(BACKUP_DIR)" ]; then echo "hosted-backup requires BACKUP_DIR=/path/to/backup" >&2; exit 1; fi; \
	backup_dir="$(BACKUP_DIR)"; \
	mkdir -p "$$backup_dir"; \
	backup_dir="$$(cd "$$backup_dir" && pwd -P)"; \
	stamp="$$(date -u +%Y%m%dT%H%M%SZ)"; \
	database_dump="$$backup_dir/postgres-$$stamp.dump"; \
	application_files="$$backup_dir/application-files-$$stamp.tar"; \
	manifest="$$backup_dir/manifest-$$stamp.sha256"; \
	restore_stack() { \
	  status="$$?"; \
	  trap - EXIT INT TERM; \
	  restore_status=0; \
	  if ! $(HOSTED_COMPOSE) up --detach --wait; then restore_status=1; fi; \
	  if [ "$$status" -ne 0 ]; then exit "$$status"; fi; \
	  exit "$$restore_status"; \
	}; \
	trap restore_stack EXIT INT TERM; \
	$(HOSTED_COMPOSE) stop caddy web api; \
	$(HOSTED_COMPOSE) exec -T postgres sh -c 'PGPASSWORD="$${POSTGRES_PASSWORD}" pg_dump --format=custom --username="$${POSTGRES_USER}" --dbname="$${POSTGRES_DB}"' >"$$database_dump"; \
	$(HOSTED_COMPOSE) run --rm --no-deps -T api tar -C /var/lib/ai-video-preproduction -cf - . >"$$application_files"; \
	( cd "$$backup_dir"; if command -v sha256sum >/dev/null 2>&1; then sha256sum "$$(basename "$$database_dump")" "$$(basename "$$application_files")"; else shasum -a 256 "$$(basename "$$database_dump")" "$$(basename "$$application_files")"; fi ) >"$$manifest"

hosted-down: hosted-env-file
	$(HOSTED_COMPOSE) down

rc-check: db-up db-upgrade-test db-current-test
	@set -euo pipefail; \
	rc_dir="$(CURDIR)/.local/rc"; \
	api_pid_file="$$rc_dir/check-api.pid"; \
	web_pid_file="$$rc_dir/check-web.pid"; \
	api_owner_file="$$rc_dir/check-api.owner"; \
	web_owner_file="$$rc_dir/check-web.owner"; \
	api_pid=""; web_pid=""; cleanup_failed=0; \
	pid_is_live() { \
	  pid="$$1"; \
	  case "$$pid" in ''|*[!0-9]*) return 1;; esac; \
	  kill -0 "$$pid" 2>/dev/null; \
	}; \
	process_owned() { \
	  pid="$$1"; marker_file="$$2"; \
	  if ! pid_is_live "$$pid" || ! test -s "$$marker_file"; then return 1; fi; \
	  IFS='|' read -r marker_pid marker_start marker_service marker_port marker_pattern < "$$marker_file"; \
	  [ "$$marker_pid" = "$$pid" ] && [ -n "$$marker_start" ] && [ -n "$$marker_port" ] && [ -n "$$marker_pattern" ] || return 1; \
	  current_start="$$(ps -p "$$pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//; s/[[:space:]]*$$//' || true)"; \
	  current_command="$$(ps -p "$$pid" -o command= 2>/dev/null || true)"; \
	  [ "$$current_start" = "$$marker_start" ] || return 1; \
	  case "$$marker_service" in api|web) ;; *) return 1;; esac; \
	  case "$$current_command" in *"$$marker_pattern"*) ;; *) return 1;; esac; \
	}; \
	write_owner_marker() { \
	  pid="$$1"; service="$$2"; port="$$3"; pattern="$$4"; marker_file="$$5"; \
	  for attempt in $$(seq 1 20); do \
	    marker_start="$$(ps -p "$$pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//; s/[[:space:]]*$$//' || true)"; \
	    marker_command="$$(ps -p "$$pid" -o command= 2>/dev/null || true)"; \
	    if [ -n "$$marker_start" ] && case "$$marker_command" in *"$$pattern"*) true;; *) false;; esac; then \
	      printf '%s|%s|%s|%s|%s\n' "$$pid" "$$marker_start" "$$service" "$$port" "$$pattern" >"$$marker_file"; \
	      return 0; \
	    fi; \
	    sleep 0.1; \
	  done; \
	  return 1; \
	}; \
	stop_pid() { \
	  pid="$$1"; marker_file="$$2"; \
	  if ! pid_is_live "$$pid"; then return 0; fi; \
	  if ! process_owned "$$pid" "$$marker_file"; then echo "Refusing to stop live unowned RC PID $$pid" >&2; return 2; fi; \
	  kill "$$pid" 2>/dev/null || true; \
	  for attempt in $$(seq 1 50); do \
	    if ! pid_is_live "$$pid"; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  kill -KILL "$$pid" 2>/dev/null || true; \
	  for attempt in $$(seq 1 20); do \
	    if ! pid_is_live "$$pid"; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  echo "Owned RC PID $$pid did not exit after SIGKILL" >&2; return 1; \
	}; \
	prepare_existing() { \
	  pid_file="$$1"; marker_file="$$2"; \
	  if test -s "$$pid_file" && pid_is_live "$$(cat "$$pid_file")"; then \
	    pid="$$(cat "$$pid_file")"; \
	    if ! process_owned "$$pid" "$$marker_file"; then echo "Refusing to replace live unowned RC PID $$pid" >&2; return 2; fi; \
	    if ! stop_pid "$$pid" "$$marker_file"; then return 1; fi; \
	  fi; \
	  rm -f "$$pid_file" "$$marker_file"; \
	}; \
	cleanup() { \
	  status="$$?"; \
	  trap - EXIT INT TERM; \
	  if [ -n "$$api_pid" ] && ! stop_pid "$$api_pid" "$$api_owner_file"; then cleanup_failed=1; fi; \
	  if [ -n "$$web_pid" ] && ! stop_pid "$$web_pid" "$$web_owner_file"; then cleanup_failed=1; fi; \
	  if [ "$$cleanup_failed" -eq 0 ]; then rm -f "$$api_pid_file" "$$api_owner_file" "$$web_pid_file" "$$web_owner_file"; fi; \
	  if [ "$$status" -eq 0 ] && [ "$$cleanup_failed" -ne 0 ]; then status=1; fi; \
	  exit "$$status"; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	mkdir -p "$$rc_dir" "$(RC_CHECK_STORAGE_ROOT)"; \
	prepare_existing "$$api_pid_file" "$$api_owner_file"; \
	prepare_existing "$$web_pid_file" "$$web_owner_file"; \
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
	if ! write_owner_marker "$$api_pid" api "$(RC_CHECK_API_PORT)" "uvicorn services.api.app.main:app" "$$api_owner_file"; then echo "RC check API ownership marker could not be established" >&2; exit 1; fi; \
	nohup env \
	  APP_ENVIRONMENT=local \
	  API_BASE_URL="$(RC_CHECK_API_BASE_URL)" \
	  PUBLIC_API_BASE_URL="$(RC_CHECK_API_BASE_URL)" \
	  WEB_HOST=127.0.0.1 \
	  WEB_PORT="$(RC_CHECK_WEB_PORT)" \
	  $(NODE_RUNNER) npm --workspace @foundation/web run start \
	  >"$$rc_dir/check-web.log" 2>&1 & \
	web_pid="$$!"; echo "$$web_pid" >"$$web_pid_file"; \
	if ! write_owner_marker "$$web_pid" web "$(RC_CHECK_WEB_PORT)" "@foundation/web" "$$web_owner_file"; then echo "RC check web ownership marker could not be established" >&2; exit 1; fi; \
	ready=0; \
	for attempt in $$(seq 1 60); do \
	  if curl --connect-timeout 2 --max-time 10 --fail --silent "$(RC_CHECK_API_BASE_URL)/api/v1/health" | grep -q '"service":"foundation-api"' && curl --connect-timeout 2 --max-time 10 --fail --silent "$(RC_CHECK_WEB_BASE_URL)" >/dev/null; then \
	    ready=1; break; \
	  fi; \
	  sleep 1; \
	done; \
	if [ "$$ready" -ne 1 ]; then echo "RC check readiness failed; inspect $$rc_dir/check-api.log and $$rc_dir/check-web.log" >&2; exit 1; fi; \
	RC_API_BASE_URL="$(RC_CHECK_API_BASE_URL)" RC_WEB_BASE_URL="$(RC_CHECK_WEB_BASE_URL)" $(UV_RUN) python infra/scripts/rc_socket_smoke.py

rc-down:
	@set -euo pipefail; \
	rc_dir="$(CURDIR)/.local/rc"; \
	pid_is_live() { \
	  pid="$$1"; \
	  case "$$pid" in ''|*[!0-9]*) return 1;; esac; \
	  kill -0 "$$pid" 2>/dev/null; \
	}; \
	process_owned() { \
	  pid="$$1"; marker_file="$$2"; \
	  if ! pid_is_live "$$pid" || ! test -s "$$marker_file"; then return 1; fi; \
	  IFS='|' read -r marker_pid marker_start marker_service marker_port marker_pattern < "$$marker_file"; \
	  [ "$$marker_pid" = "$$pid" ] && [ -n "$$marker_start" ] && [ -n "$$marker_port" ] && [ -n "$$marker_pattern" ] || return 1; \
	  current_start="$$(ps -p "$$pid" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//; s/[[:space:]]*$$//' || true)"; \
	  current_command="$$(ps -p "$$pid" -o command= 2>/dev/null || true)"; \
	  [ "$$current_start" = "$$marker_start" ] || return 1; \
	  case "$$marker_service" in api|web) ;; *) return 1;; esac; \
	  case "$$current_command" in *"$$marker_pattern"*) ;; *) return 1;; esac; \
	}; \
	stop_pid() { \
	  pid="$$1"; marker_file="$$2"; \
	  if ! pid_is_live "$$pid"; then return 0; fi; \
	  if ! process_owned "$$pid" "$$marker_file"; then echo "Refusing to stop live unowned RC PID $$pid" >&2; return 2; fi; \
	  kill "$$pid" 2>/dev/null || true; \
	  for attempt in $$(seq 1 50); do \
	    if ! pid_is_live "$$pid"; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  kill -KILL "$$pid" 2>/dev/null || true; \
	  for attempt in $$(seq 1 20); do \
	    if ! pid_is_live "$$pid"; then return 0; fi; \
	    sleep 0.1; \
	  done; \
	  echo "Owned RC PID $$pid did not exit after SIGKILL" >&2; return 1; \
	}; \
	stop_failed=0; \
	for service in api web; do \
	  pid_file="$$rc_dir/$$service.pid"; \
	  owner_file="$$rc_dir/$$service.owner"; \
	  if test -s "$$pid_file" && pid_is_live "$$(cat "$$pid_file")"; then \
	    if ! stop_pid "$$(cat "$$pid_file")" "$$owner_file"; then stop_failed=1; else rm -f "$$pid_file" "$$owner_file"; fi; \
	  else \
	    rm -f "$$pid_file" "$$owner_file"; \
	  fi; \
	done; \
	if [ "$$stop_failed" -ne 0 ]; then exit 1; fi
	$(MAKE) db-down
