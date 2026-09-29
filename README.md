# AI Control Center

One central web app for connecting multiple **authorized** AI provider accounts, queuing jobs across them, and browsing every result in a single gallery.

```
                    CENTRAL DASHBOARD  (Next.js)
                           |
                    FastAPI  /api  ── auth · accounts · jobs · gallery · usage
                           |
          +----------------+----------------+
          |                                 |
     Redis job queue  ─────────►  Worker(s)  ──►  ProviderAdapter ──► OpenAI (official API)
          |                                 |          (mock, future providers…)
     PostgreSQL  ◄──── job state, usage ────+
                                            └──►  Object storage (local disk, S3, or R2)
```

It uses **official APIs only**: no cookies, no session-token extraction, no CAPTCHA or bot-detection bypass, no scraping, and no attempts to get around provider limits. When a provider answers HTTP 429, the account rests for exactly the window the provider specified.

## 1. What it does

- **Register / sign in** with Argon2-hashed passwords and revocable HTTP-only session cookies.
- **Connect provider accounts** by API key. Keys are verified with the provider, encrypted (Fernet) before storage, and never returned to the browser.
- **Create jobs** (image generation): choose provider/model or leave them on *Auto*, and pick 1–10 outputs. Requests return immediately; a worker does the slow part.
- **Auto routing** picks an account that supports the model, has valid credentials, is not inside a provider rate-limit window, and was used least recently.
- **Retries** with bounded attempts: rate limits honor the provider's `Retry-After`; transient failures back off exponentially; bad requests fail fast.
- **Gallery** with search, preview, download, copy prompt, delete, and multi-select bulk download (zip) and delete.
- **Usage** page showing real request/image/token counts recorded by this app plus any rate limits the provider reports. It never invents numbers: if a provider exposes no usage data it says *"Usage information unavailable for this provider."*
- **Audit log**, dark mode, responsive layout.

## 2. Architecture

| Layer | Tech |
| --- | --- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui, SWR |
| API | FastAPI, SQLAlchemy 2, Alembic |
| Data | PostgreSQL (SQLite for local dev/tests) |
| Queue | Redis list + sorted set (delayed retries) |
| Workers | `python -m app.workers.worker` (or embedded thread for dev) |
| Providers | `app/providers/*` adapters behind one interface |
| Storage | `app/services/storage.py` (local disk, S3, R2) |

The browser only talks to the Next.js origin; `/api/*` is proxied to FastAPI, so the session cookie is same-origin. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
backend/    FastAPI app, workers, migrations, tests
frontend/   Next.js app
docker/     production compose override
docs/       ARCHITECTURE · API · DEVELOPMENT · SECURITY
scripts/    generate_env.py, validate_config.py
```

## 3. Requirements

- Python 3.12+ and Node.js 20+ (24 tested)
- Docker (recommended) **or** local PostgreSQL 16 + Redis 7
- No Docker/Postgres/Redis? Local development also works with SQLite and an in-process Redis, see [Running locally](#6-running-locally).

## 4. Installation

```bash
git clone https://github.com/mdperves06/multimodel.git
cd multimodel

python -m venv backend/.venv
backend/.venv/Scripts/activate            # Windows. macOS/Linux: source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt

cd frontend && npm install && cd ..
python scripts/generate_env.py            # creates .env with fresh secrets
```

## 5. Environment variables

`python scripts/generate_env.py` copies [.env.example](.env.example) to `.env` and fills in secrets. Key variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://…`, or `sqlite:///./dev.db` for local dev) |
| `REDIS_URL` | Redis URL. `memory://` = in-process Redis for local dev only (refused in production) |
| `JWT_SECRET` | ≥ 32 chars; signs session tokens (required) |
| `ENCRYPTION_KEY` | Fernet key that encrypts provider credentials (required, **back it up**) |
| `CORS_ORIGINS` / `ALLOWED_HOSTS` | Allowed browser origins / Host headers |
| `TRUST_PROXY` | Honor `X-Forwarded-For` (only behind a trusted proxy) |
| `STORAGE_TYPE`, `STORAGE_LOCAL_PATH` | Object storage: `local`, `s3`, or `r2` |
| `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_ENDPOINT_URL`, `STORAGE_REGION` | S3/R2 credentials; the endpoint is required for R2 |
| `OPENAI_API_KEY` | Only used by the opt-in live check script; users add keys in the UI |
| `ENABLE_MOCK_PROVIDER` | Development/test-only mock provider (refused in production) |
| `EMBEDDED_WORKER` | Run the worker inside the API process (dev convenience) |

The app refuses to start if secrets are missing/invalid, and in production if it is configured with SQLite, in-memory Redis, or the mock provider.

## 6. Running locally

**Fastest path (no Docker, no Postgres/Redis):** set these in `.env`, then run two commands.

```dotenv
DATABASE_URL=sqlite:///./dev.db
REDIS_URL=memory://
EMBEDDED_WORKER=true
ENABLE_MOCK_PROVIDER=true     # optional: lets you try the UI without spending API credits
```

```bash
cd backend && alembic upgrade head && uvicorn app.main:app --reload     # http://localhost:8000
cd frontend && npm run dev                                               # http://localhost:3000
```

Open http://localhost:3000, register, click **Connect Provider**, and create a job. With the mock provider any key such as `mock-abc12345` works; `mock-ratelimit` simulates HTTP 429.

**With real Postgres/Redis:** `docker compose up -d postgres redis`, use the default `DATABASE_URL`/`REDIS_URL`, drop `EMBEDDED_WORKER`, and run the worker in a third terminal: `cd backend && python -m app.workers.worker`.

**Try the real OpenAI API** (opt-in, one cheap call):

```bash
OPENAI_API_KEY=sk-... python backend/scripts/openai_live_check.py            # validates the key (free)
OPENAI_API_KEY=sk-... python backend/scripts/openai_live_check.py --generate # one 256px image (billed)
```

## 7. Docker setup

```bash
python scripts/generate_env.py
docker compose up --build
```

Starts `postgres`, `redis`, `backend` (runs migrations, then serves :8000), `worker`, and `frontend` (:3000). Images run as non-root and have health checks. Generated images live in the `storage` volume shared by API and worker. Add `ENABLE_MOCK_PROVIDER=true` to `.env` to try the mock provider.

> Docker was not available in the environment this project was built in, so the Compose stack and Dockerfiles have been validated structurally (`scripts/validate_config.py`, CI builds them) but not run end to end here. If `docker compose up` misbehaves on your machine, please open an issue with the logs.

## 8. Adding providers

1. Create `backend/app/providers/acme.py` with a class extending `ProviderAdapter` (`app/providers/base.py`): declare `slug`, `name`, `capabilities`, `models`, and implement `validate_credentials`, `generate_image`, `get_usage`, `get_limits`. Raise `ProviderRateLimitError(retry_after=…)`, `ProviderAuthError`, `ProviderTransientError`, or `ProviderRequestError`; the job system handles the rest.
2. Register it in `app/providers/registry.py` (one line).
3. Restart the API. It is synced into the `providers` table and appears in the UI.
4. Add tests with `httpx.MockTransport`, following `tests/test_openai_adapter.py`.

No job, queue, or UI code changes are needed. Details: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## 9. Running tests

```bash
cd backend
pytest -q && ruff check . && mypy app && pip-audit -r requirements.txt

cd ../frontend
npm run check          # lint + typecheck + unit tests + production build
```

The backend suite (90 tests) covers registration, login, authorization and isolation between users, provider connection, invalid credentials, job creation, queue processing, provider selection, rate-limit handling, retry logic, result storage, account deletion, security headers, redaction, and migrations. It runs on SQLite with an in-process Redis; provider HTTP is mocked at the transport layer in tests only.

## 10. Production deployment

```bash
docker compose -f docker-compose.yml -f docker/docker-compose.prod.yml up -d --build
```

Checklist:

- Put a TLS-terminating reverse proxy in front of the frontend (:3000). Secure cookies and HSTS assume HTTPS.
- Set `ENVIRONMENT=production`, a strong `POSTGRES_PASSWORD`, `ALLOWED_HOSTS`, and `CORS_ORIGINS` (the public https origin). The production override requires them.
- **Back up `ENCRYPTION_KEY` and the Postgres volume.** Without the key, stored provider credentials cannot be decrypted.
- Run more workers by scaling the service: `docker compose up -d --scale worker=3`.
- Local-disk storage is per-host. For multi-host deployments set `STORAGE_TYPE=s3` (or `r2` with `STORAGE_ENDPOINT_URL`) and the bucket credentials.
- Read [docs/SECURITY.md](docs/SECURITY.md) for the threat model and known limitations.

## Known limitations

- Image generation is the only task type; the adapter interface is ready for more.
- The OpenAI adapter is verified against mocked HTTP responses matching the documented API; run the live check with your own key to confirm end to end. OpenAI does not expose usage totals to ordinary API keys, so provider-reported usage is shown as unavailable.
- Jobs lost from Redis (e.g. an unpersisted Redis restart) are not automatically re-queued; use the *Retry* action on stuck jobs.
