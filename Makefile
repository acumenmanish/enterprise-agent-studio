.PHONY: up down reset-data logs test lint fmt

up:
	docker compose up --build

down:
	docker compose down

reset-data:
	docker compose down -v

logs:
	docker compose logs -f

test:
	cd platform/backend && python3 -m pytest tests/ -v

lint:
	cd platform/backend && ruff check .

fmt:
	cd platform/backend && ruff check --fix .
