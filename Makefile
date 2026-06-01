# dz-dashboard — Phase 2 operations
# One-command entry points for the two-process dashboard (BFF + SPA).
# See docs/PHASE2_RUNBOOK.md for the day-2 playbook.

.DEFAULT_GOAL := help
.PHONY: help install dev serve build-web gen-api gate check \
        test test-backend test-frontend test-e2e e2e-update clean

WEB := web

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) + frontend (npm) deps from a fresh checkout
	uv sync --extra dev
	cd $(WEB) && npm ci

dev: ## Run BFF (:8800, reload) + Vite dev server (:5173) together; Ctrl-C stops both
	@echo "BFF  -> http://127.0.0.1:8800   SPA -> http://127.0.0.1:5173"
	@trap 'kill 0' EXIT INT TERM; \
		uv run dz-dashboard serve --reload & \
		( cd $(WEB) && npm run dev ) & \
		wait

serve: build-web ## Production-ish local run: one uvicorn serving the built SPA single-origin (:8800)
	@echo "Dashboard -> http://127.0.0.1:8800 (API + SPA, single origin)"
	uv run dz-dashboard serve --static $(WEB)/dist

build-web: ## Build the SPA into web/dist
	cd $(WEB) && npm run build

gen-api: ## Regenerate the typed API client from the live BFF (must be running on :8800)
	cd $(WEB) && npm run gen:api

gate: check ## Alias for `check`
check: ## Full green gate, both domains (must pass before commit)
	uv run pytest
	uv run ruff check
	uv run ruff format --check
	uv run mypy src/
	cd $(WEB) && npm run typecheck && npm run test

test: test-backend test-frontend ## Run backend + frontend unit/contract tests

test-backend: ## Backend unit + contract tests
	uv run pytest

test-frontend: ## Frontend component + feature tests
	cd $(WEB) && npm run test

test-e2e: ## Playwright e2e + visual-regression (boots BFF+SPA on the fixture DB)
	cd $(WEB) && npm run test:e2e

e2e-update: ## Refresh Playwright visual-regression snapshots
	cd $(WEB) && npm run test:e2e:update

clean: ## Remove build artifacts and tool caches (keeps deps installed)
	rm -rf $(WEB)/dist $(WEB)/playwright-report $(WEB)/test-results
	rm -rf .pytest_cache .ruff_cache .mypy_cache
