# PathWise AI — Makefile

.PHONY: help build up down dev test lint generate-data train evaluate verify clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ──────────────────────────────────────────────
build: ## Build all Docker images
	docker compose build

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

dev: ## Start with hot-reload (development mode)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

infra: ## Start only infrastructure (DB + Redis)
	docker compose up -d timescaledb redis

logs: ## Tail logs from all services
	docker compose logs -f

# ── Testing ─────────────────────────────────────────────
test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests (requires Redis)
	pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests
	pytest tests/e2e/ -v

# ── ML Pipeline ─────────────────────────────────────────
generate-data: ## Generate synthetic telemetry data (1 hour)
	python ml/scripts/generate_synthetic_data.py --duration-hours 1

generate-data-full: ## Generate full synthetic data (30 days)
	python ml/scripts/generate_synthetic_data.py --duration-hours 720

train: ## Train the LSTM model
	python ml/scripts/train.py

train-smoke: ## Quick training smoke test
	python ml/scripts/train.py --smoke-test --epochs 2

evaluate: ## Evaluate the trained model
	python ml/scripts/evaluate.py

# ── Code Quality ────────────────────────────────────────
lint: ## Lint Python code with ruff
	ruff check services/ tests/ ml/

lint-fix: ## Auto-fix lint issues
	ruff check --fix services/ tests/ ml/

# ── Utilities ───────────────────────────────────────────
verify: ## Verify project structure
	python build_orchestrator.py

clean: ## Remove generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf ml/data/synthetic/*.parquet
	rm -rf ml/checkpoints/*.pt
	rm -rf frontend/build/
	rm -rf frontend/node_modules/
