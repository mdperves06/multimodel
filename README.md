# AI Control Center

A central web app for connecting multiple **authorized** AI provider accounts (official APIs / OAuth only), queuing jobs across them, and browsing results in one gallery. Provider-agnostic; OpenAI is the first adapter (Phase 6).

> Status: **Phase 1 – scaffold.** Later phases add auth, database, providers, queue, and the full dashboard.

## Structure

```
backend/    FastAPI + SQLAlchemy + Alembic (Python)
frontend/   Next.js + TypeScript + Tailwind + shadcn/ui
docker/     extra Docker assets
docs/       architecture, API, development, security docs
docker-compose.yml   postgres, redis, backend, frontend
```

## Requirements

Node 20+ (24 tested), Python 3.12+, and either Docker (recommended) or local PostgreSQL 16 + Redis 7.

## Run locally

```bash
cp .env.example .env
```

Backend (http://localhost:8000, health at `/api/health`):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate      # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (http://localhost:3000):

```bash
cd frontend
npm install
npm run dev
```

## Docker

```bash
docker compose up --build
```

Starts postgres, redis, backend (:8000) and frontend (:3000).

## Checks

```bash
cd backend && pytest && ruff check . && mypy app
cd frontend && npm run lint && npm run build
```

## Security

Never commit `.env`. Only official APIs are used; no cookies, session tokens, or bot-detection bypass.
