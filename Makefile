.DEFAULT_GOAL := help
.SHELLFLAGS := -eu -c

COMPOSE := docker compose
ALL_PROFILES := --profile demo --profile live --profile tools
PYTHON ?= .venv/bin/python

.PHONY: help install lint test qa demo demo-detached live live-detached db schema etl smoke-fixture validate logs down

help: ## Show the supported local workflows.
	@printf '%s\n' \
	  'Instacart Decision Intelligence' \
	  '' \
	  '  make install        Create .venv and install application + dev dependencies' \
	  '  make qa             Run Ruff and the complete deterministic test suite' \
	  '  make demo           Build and run the deterministic demo at localhost:8501' \
	  '  make demo-detached  Run the demo in the background and wait for health' \
	  '  make db             Start the MariaDB live-profile dependency' \
	  '  make schema         Apply the idempotent warehouse schema files' \
	  '  make etl            Load ./data into MariaDB through the packaged ETL CLI' \
	  '  make smoke-fixture  Prove schema + ETL contracts in an isolated temp stack' \
	  '  make live           Run the fail-closed live dashboard (requires loaded data)' \
	  '  make live-detached  Run the live stack in the background' \
	  '  make validate       Validate shell and Compose configuration' \
	  '  make logs           Follow dashboard and database logs' \
	  '  make down           Stop containers while preserving warehouse data'

install: ## Create an isolated Python environment and install dev dependencies.
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install --editable '.[dev]'

lint: ## Run static analysis across application and test code.
	$(PYTHON) -m ruff check etl dashboard mining tests

test: ## Run every deterministic unit, contract, and dashboard smoke test.
	MPLBACKEND=Agg $(PYTHON) -m pytest -W error::FutureWarning

qa: lint test ## Run the local quality gate used before commits.

demo: ## Run the deterministic representative snapshot in the foreground.
	$(COMPOSE) --profile demo up --build dashboard-demo

demo-detached: ## Run the demo in the background and wait for its healthcheck.
	$(COMPOSE) --profile demo up --build --detach --wait dashboard-demo
	@printf 'Demo ready: http://localhost:%s\n' "$${DASHBOARD_PORT:-8501}"

db: ## Start MariaDB and wait until schema initialization is healthy.
	$(COMPOSE) --profile live up --detach --wait mariadb

schema: db ## Reapply idempotent schema files to the running MariaDB container.
	./sql/run_all_sql.sh

etl: schema ## Load the six local source CSV files through the project CLI.
	@test -d data || { printf '%s\n' 'Missing ./data; add the six Instacart CSV files first.' >&2; exit 1; }
	$(COMPOSE) --profile live --profile tools run --rm --build etl

smoke-fixture: ## Exercise schema, ETL, and quality checks in an isolated stack.
	./scripts/smoke_fixture.sh

live: ## Run MariaDB and the fail-closed live dashboard in the foreground.
	@printf '%s\n' 'Live mode requires a completed `make etl` load.'
	$(COMPOSE) --profile live up --build mariadb dashboard-live

live-detached: ## Run the live stack in the background and wait for healthchecks.
	@printf '%s\n' 'Live mode requires a completed `make etl` load.'
	$(COMPOSE) --profile live up --build --detach --wait mariadb dashboard-live
	@printf 'Live dashboard ready: http://localhost:%s\n' "$${DASHBOARD_PORT:-8501}"

validate: ## Validate scripts and the fully expanded Compose model.
	bash -n run_dashboard.sh sql/run_all_sql.sh
	$(COMPOSE) $(ALL_PROFILES) config --quiet

logs: ## Follow logs for either active dashboard and MariaDB.
	$(COMPOSE) $(ALL_PROFILES) logs --follow dashboard-demo dashboard-live mariadb

down: ## Stop all project containers; the named MariaDB volume is retained.
	$(COMPOSE) $(ALL_PROFILES) down --remove-orphans
