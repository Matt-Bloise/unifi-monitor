.PHONY: install dev run test lint docker-up docker-down

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

run:
	python -m unifi_monitor

test:
	python -m pytest tests/ -v

lint:
	find src/ tests/ -name '*.py' | xargs -I{} python3 -m py_compile {}
	@echo "All files compile OK"

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
