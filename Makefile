.PHONY: up down build logs test lint format admin backup

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=200

test:
	docker compose run --rm backend pytest

lint:
	docker compose run --rm backend ruff check app tests

format:
	docker compose run --rm backend ruff format app tests

admin:
	@echo "Usage: docker compose exec backend python -m app.cli create-admin --email you@example.com --password '...' --organization 'CodeMorf'"

backup:
	./scripts/backup.sh
