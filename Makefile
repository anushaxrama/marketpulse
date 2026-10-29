.PHONY: demo replay benchmark test test-integration test-browser verify stop logs
SCENARIO ?= duplicate
WINDOW ?= 5
WATERMARK ?= 10

demo:
	MP_LAB_ENABLED=true docker compose up -d --build
	docker compose exec -T api marketpulse demo

replay:
	docker compose exec -T api marketpulse replay --scenario $(SCENARIO) --window $(WINDOW) --watermark $(WATERMARK)

benchmark:
	docker compose exec -T api marketpulse benchmark --scenario baseline

test:
	uv sync --frozen --extra dev
	uv run pytest -q
	uv run ruff check marketpulse services tests scripts infra
	uv run mypy marketpulse services
	pnpm --dir apps/dashboard install --frozen-lockfile
	pnpm --dir apps/dashboard typecheck
	pnpm --dir apps/dashboard test

test-integration:
	MP_TEST_DATABASE_URL=postgresql://marketpulse:marketpulse_local@127.0.0.1:5546/marketpulse_test uv run pytest -q

test-browser:
	PLAYWRIGHT_USE_CHROME=1 pnpm --dir apps/dashboard test:e2e

verify:
	uv run python scripts/verify_streaming.py

logs:
	docker compose logs -f runner

stop:
	docker compose stop
