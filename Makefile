SHELL := /bin/zsh

NODE_RUNNER := ./scripts/run-with-node.sh
UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
UV_RUN := UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --frozen --offline
PYTHONPATH := $(CURDIR):$(CURDIR)/packages/contracts/python:$(CURDIR)/packages/model-registry:$(PYTHONPATH)

-include .env
export

.PHONY: setup dev-web dev-api dev-worker dev format format-check lint typecheck test contract-check build check

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

check: format-check lint typecheck test contract-check build
