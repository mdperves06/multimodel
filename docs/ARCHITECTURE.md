# Architecture

## Request flow

```
Browser ──► Next.js (:3000) ──/api/* rewrite──► FastAPI (:8000)
                                                   │
             POST /api/jobs  ──► validate ──► INSERT job (queued) ──► RPUSH acc:queue
                                                   │
Worker: BLPOP ─► claim job (UPDATE … WHERE status IN (queued, retrying))
                 ─► select account ─► decrypt credentials ─► ProviderAdapter.generate_image
                 ─► storage.put(bytes) ─► INSERT job_outputs (key + metadata) ─► status=completed
```

The browser never sees the FastAPI origin. The Next.js server proxies `/api/*`, which keeps the HTTP-only session cookie same-origin and removes the need for browser CORS.

## Backend layout (`backend/app`)

| Package | Responsibility |
| --- | --- |
| `main.py`, `config.py`, `db.py`, `redis_client.py`, `errors.py` | app factory, validated settings, engine/session, Redis, error handlers |
| `api/` | thin HTTP routers: `auth`, `providers`, `accounts`, `jobs`, `gallery`, `usage`, `audit` |
| `schemas/` | Pydantic request/response models (credentials never appear in responses) |
| `models/` | SQLAlchemy entities: `User`, `Provider`, `ConnectedAccount`, `Job`, `JobOutput`, `UsageRecord`, `AuditLog` |
| `services/` | business logic: `jobs`, `accounts`, `selection`, `usage`, `storage`, `audit`, `providers` |
| `providers/` | `base.py` (contract), `openai.py`, `mock.py`, `registry.py` |
| `workers/` | `queue.py` (Redis), `processor.py` (run one job), `worker.py` (loop, recovery) |
| `security/` | passwords, tokens, credential encryption, auth dependency, rate limiting, headers, CSRF, redaction |

Routers call services; services call providers/storage/queue. Provider-specific code never appears outside `providers/`.

## Data model

```
User 1─* ConnectedAccount *─1 Provider
User 1─* Job 1─* JobOutput
ConnectedAccount 1─* UsageRecord
AuditLog (user_id nullable)
```

- Enumerations (`status`) are plain strings validated in code, so adding a state needs no PostgreSQL enum migration.
- `job_outputs` stores `storage_key`, `mime_type`, `size_bytes`, `metadata`, `created_at`. Image bytes live only in object storage.
- Deleting a connected account removes its credentials and usage rows; jobs and outputs are kept (`jobs.account_id` becomes NULL; `provider_used`/`account_label` are denormalised for history).
- All timestamps are timezone-aware UTC (`UTCDateTime` type also fixes SQLite's tz loss).

## Job lifecycle

```
queued ─► processing ─► completed
   ▲          │  ├────► failed
   │          │  └────► cancelled
   └─ retrying ◄──────── (429 / transient / auth-failed with alternatives)
```

Timeline events are stored on the job (`created → queued → processing → generating → storing → completed`, plus `retrying`, `failed`, `cancelled`) and rendered by the job detail page.

**Claiming.** A worker does an atomic `UPDATE … WHERE status IN ('queued','retrying')`; only one wins, so duplicate queue entries and multiple workers are safe.

**Partial progress.** Work is done in provider-sized batches (e.g. DALL·E 3 allows 1 image per request). Each batch is stored immediately. A retry only generates the *remaining* outputs, so paid images are never lost or duplicated.

**Cancellation.** Checked before and after each provider call. Results that arrive after a cancel are discarded (the request is still recorded as usage, because it really happened).

**Recovery.** On start a worker re-queues jobs stuck in `processing` for > 15 minutes.

## Provider selection (`services/selection.py`)

For `provider="auto"` (or an explicit provider), an account is eligible when it belongs to the user, its adapter supports the capability and requested model, `status == active`, it is not inside a `rate_limited_until` window, and the provider has not reported zero remaining requests for a window that has not yet reset. Eligible accounts are ordered by least-recently-used. If none is eligible only because of rate limits, the job waits for the earliest window to end; otherwise it fails with an actionable message.

## Rate limits and retries (`workers/processor.py`)

| Provider outcome | Behaviour |
| --- | --- |
| HTTP 429 | account blocked until `now + retry_after` (from `Retry-After` / `x-ratelimit-reset-*`); job moves to another eligible account or waits for the earliest window |
| 429 `insufficient_quota` | treated as a 1-hour block (billing problem, not a burst) |
| 401 | account flagged `invalid`; job tries another account or fails |
| 5xx / timeout / network | exponential backoff `5·2ⁿ` s (max 300 s) |
| 4xx request errors | job fails immediately with the provider's message |

All retries are bounded by `MAX_JOB_ATTEMPTS` (default 5). The system never retries an account before the provider's window ends.

## Usage accounting

`usage_records` is written per real provider request: requests, images, and tokens *only when the provider returns them* (else NULL, shown as "—"). Provider-reported usage/limits are surfaced only if the adapter can fetch them; OpenAI's usage endpoints need organisation admin keys, so it reports "unavailable".

## Frontend

App Router with two route groups: `(auth)` (login/register) and `(app)` (shell with sidebar/topbar). Data uses SWR against `/api` with polling while jobs are active. `proxy.ts` provides an optimistic redirect based on cookie presence; the API enforces real authentication on every call, and a 401 clears the stale cookie via `/api/auth/logout` and returns to sign-in.
