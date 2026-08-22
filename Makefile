.PHONY: install install-clients dev test lint format typecheck typecheck-clients build-web build-admin verify migrate migration bootstrap up down logs prod-config

install:
	python -m pip install -r backend/requirements-dev.txt

install-clients:
	npm ci

dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && pytest

lint:
	cd backend && ruff check app tests migrations

format:
	cd backend && ruff format app tests migrations

typecheck:
	cd backend && mypy app

typecheck-clients:
	npm run typecheck:clients

build-web:
	npm run build --workspace @drovixa/web

build-admin:
	npm run build --workspace @drovixa/admin

verify: lint typecheck test typecheck-clients build-web build-admin

migrate:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(m)"

bootstrap:
	cd backend && python -m app.scripts.bootstrap_superuser

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend worker scheduler admin web

prod-config:
	docker compose --env-file deploy/production/.env.production -f deploy/production/compose.yml config --quiet
