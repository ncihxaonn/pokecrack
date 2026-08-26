SHELL := /usr/bin/env bash
PNPM ?= pnpm
UV ?= uv
SUPABASE ?= npx --yes supabase@2.115.0
DEPLOY_SHA ?= 0000000000000000000000000000000000000000

.PHONY: install lint typecheck test build verify policy db-test compose-config compose-build demo

install:
	$(PNPM) install --frozen-lockfile
	cd services/worker && $(UV) sync --frozen --extra dev
	cd services/auth-browser && $(UV) sync --frozen --extra dev

lint:
	$(PNPM) lint
	cd services/worker && $(UV) run ruff check pokecrack_worker tests && $(UV) run ruff format --check pokecrack_worker tests
	cd services/auth-browser && $(UV) run ruff check src tests && $(UV) run ruff format --check src tests

typecheck:
	$(PNPM) typecheck
	cd services/worker && $(UV) run mypy pokecrack_worker
	cd services/auth-browser && $(UV) run mypy src/pokecrack_browser

test:
	$(PNPM) test
	cd services/worker && $(UV) run pytest -q
	cd services/auth-browser && $(UV) run pytest -q
	python3 -m unittest discover -s deploy/tests -v
	python3 -m unittest discover -s scripts/tests -v

build:
	$(PNPM) build

policy:
	python3 scripts/verify_repository.py .

verify: policy lint typecheck test build compose-config

db-test:
	$(SUPABASE) start
	$(SUPABASE) db reset
	$(SUPABASE) test db
	$(SUPABASE) stop --no-backup

compose-config:
	DEPLOY_SHA=$(DEPLOY_SHA) docker compose -f deploy/compose.prod.yml config --quiet

compose-build:
	DEPLOY_SHA=$(DEPLOY_SHA) docker compose -f deploy/compose.prod.yml build

demo:
	DATA_MODE=demo NEXT_PUBLIC_SITE_URL=http://localhost:3000 $(PNPM) --filter @pokecrack/web dev
