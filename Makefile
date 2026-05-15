.PHONY: install dev test test-unit test-int lint typecheck format docker-up docker-down migrate demo clean

install:
	uv sync --extra dev
	cd ui && corepack pnpm install

dev: docker-up
	uv run uvicorn platform.api.main:app --host 0.0.0.0 --port 8000 & cd ui && corepack pnpm run dev

test:
	uv run --extra dev python -m pytest tests/ -v -o addopts= || test $$? -eq 5

test-unit:
	uv run --extra dev python -m pytest tests/unit/ -v -o addopts= || test $$? -eq 5

test-int:
	uv run --extra dev python -m pytest tests/integration/ -v -o addopts= || test $$? -eq 5

lint:
	uv run --extra dev python -m ruff check platform tests alembic
	cd ui && corepack pnpm run lint

typecheck:
	uv run --extra dev python -m mypy platform alembic
	cd ui && corepack pnpm exec tsc --noEmit

format:
	uv run --extra dev python -m ruff format platform tests alembic
	cd ui && corepack pnpm run format

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

migrate:
	uv run alembic upgrade head

demo:
	uv run python -m platform.demo

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
	rm -rf .coverage htmlcov coverage.xml ui/dist ui/coverage
