.PHONY: install dev run test lint format check docker-up docker-down

install:
	pip install -e .

dev:
	pip install -e ".[dev,netflow]"

run:
	python -m unifi_monitor

test:
	python -m pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

check:
	ruff check src/ tests/
	ruff format --check src/ tests/

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
