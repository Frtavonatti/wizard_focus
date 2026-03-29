# Wizard Focus — Backend

REST API for **Wizard Focus**, a gamified focus timer app. Users start focus sessions and grow a wizard companion over time — the more they focus, the more their wizard evolves.

Built with [FastAPI](https://fastapi.tiangolo.com/) and Python 3.12.

---

## Requirements

- [uv](https://docs.astral.sh/uv/) >= 0.5
- Python 3.12

## Installation

```bash
# Clone the repo and navigate to the server folder
cd server

# Install dependencies (including dev tools)
uv sync --extra dev
```

## Running the server

```bash
uv run fastapi dev
```

The API will be available at `http://localhost:8000`.  
Interactive docs at `http://localhost:8000/docs`.

## Running tests

```bash
uv run pytest
```
