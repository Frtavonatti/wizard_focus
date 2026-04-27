.PHONY: dev start test migrate migration

dev:
	uv run fastapi dev main.py

start:
	uv run fastapi run main.py

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate
