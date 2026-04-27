.PHONY: dev start test migrate migration

dev:
	uv run fastapi dev src/main.py

start:
	uv run fastapi run src/main.py

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate
