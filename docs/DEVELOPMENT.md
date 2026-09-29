# Development guide

## Setup

```bash
python -m venv backend/.venv && backend/.venv/Scripts/activate      # macOS/Linux: source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd frontend && npm install)
python scripts/generate_env.py
```

Local mode without Docker (`.env`):

```dotenv
DATABASE_URL=sqlite:///./dev.db
REDIS_URL=memory://
EMBEDDED_WORKER=true
ENABLE_MOCK_PROVIDER=true
```

`memory://` swaps Redis for an in-process fake (dev/test only; refused in production), and the embedded worker runs jobs inside the API process, so a single `uvicorn` command is a complete backend. Paths such as `sqlite:///./dev.db` and `STORAGE_LOCAL_PATH` are relative to the directory you start the server from (`backend/`).

## Everyday commands

| Task | Command |
| --- | --- |
| API with reload | `cd backend && alembic upgrade head && uvicorn app.main:app --reload` |
| Worker (real Redis) | `cd backend && python -m app.workers.worker` |
| Frontend | `cd frontend && npm run dev` |
| Backend tests | `cd backend && pytest -q` |
| Backend lint/types | `ruff check . && ruff format . && mypy app` |
| Frontend checks | `cd frontend && npm run check` |
| Validate deploy files | `python scripts/validate_config.py` |
| End-to-end smoke (running stack, mock provider on) | `python backend/scripts/e2e_smoke.py http://localhost:3000` |
| Dependency audit | `pip-audit -r backend/requirements.txt`, `npm audit --omit=dev` |

## Database migrations

```bash
cd backend
alembic revision --autogenerate -m "describe change"    # review the generated file!
alembic upgrade head
```

`tests/test_migrations.py` fails if the models drift from the migrations, so forgetting to generate one is caught in CI.

## Adding a provider

1. **Adapter** `backend/app/providers/acme.py`

   ```python
   class AcmeAdapter(ProviderAdapter):
       slug = "acme"
       name = "Acme AI"
       models = (ModelInfo(id="acme-img-1", name="Acme Image 1", max_outputs_per_request=4,
                           sizes=("1024x1024",), default_size="1024x1024"),)

       def validate_credentials(self, credentials): ...   # cheap authenticated call, no billing
       def generate_image(self, credentials, request): ...  # ONE provider request, n <= max per request
       def get_usage(self, credentials): ...              # real data or UsageInfo(available=False, ...)
       def get_limits(self, credentials): ...
   ```

2. **Error mapping.** Translate the provider's failures to `ProviderAuthError`, `ProviderRateLimitError(message, retry_after=<seconds from the provider>)`, `ProviderQuotaError`, `ProviderTransientError` (5xx/timeouts), or `ProviderRequestError` (bad input, policy). Never include credentials in messages.
3. **Register** it in `providers/registry.py::get_registry` (one line).
4. **Test** with `httpx.MockTransport` (see `tests/test_openai_adapter.py`): success, invalid key, 429 with a retry hint, 5xx, network failure.
5. **Credentials** are stored as `{"api_key": "..."}`. If a provider needs OAuth, extend `AccountCreate` and `make_credentials` and store the token dict; the encryption layer already handles arbitrary JSON.

Use official APIs/OAuth only. Do not add cookie/session-token flows or anything that circumvents provider limits.

## Adding a storage backend

Implement `Storage` (`put/get/delete/exists`) in `services/storage.py` (for S3/R2 use boto3; R2 is S3-compatible with a custom endpoint) and return it from `get_storage()` for the matching `STORAGE_TYPE`. Nothing else changes: the DB only stores `storage_key`.

## Testing notes

- Tests run on in-memory SQLite and an in-process Redis; `conftest.py` sets safe test environment variables.
- `drain()` runs the worker synchronously; `make_all_delayed_due()` fast-forwards delayed retries.
- HTTP to providers is mocked at the `httpx` transport layer **in tests only**. Production code contains no fake responses. The `mock` provider is a separate adapter that must be enabled explicitly and is refused in production.
- The mock provider's special keys: `mock-invalid` (auth failure), `mock-ratelimit` (429, 2 s), `mock-quota` (quota), `mock-flaky` (transient).

## Conventions

- Routers stay thin; logic lives in `services/`.
- No secrets in logs, audit metadata, or error messages (`security/redaction.py` is a safety net, not a licence).
- New endpoints must scope queries by `user_id` and get a cross-user test.
