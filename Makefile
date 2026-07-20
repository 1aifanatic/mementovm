.PHONY: setup dev build lint test benchmark migrate smoke reliability replay

setup:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	npm --prefix frontend install

dev:
	docker compose up --build

build:
	npm --prefix frontend run build
	docker compose build

lint:
	.venv/bin/ruff check backend worker tests
	npm --prefix frontend run lint

test:
	.venv/bin/python -m pytest --cov=backend.app

benchmark:
	.venv/bin/python -m evaluation.runner

migrate:
	.venv/bin/alembic -c backend/alembic.ini upgrade head

smoke:
	.venv/bin/python deployment/smoke.py --base-url "$(BASE_URL)"

reliability:
	.venv/bin/python deployment/reliability_gate.py --base-url "$(BASE_URL)" --runs 10

replay:
	curl --fail -X POST "$(BASE_URL)/v1/replays/official-demo/export"
