# API reference

Base path: `/api`. JSON in/out. Interactive OpenAPI docs are served at `/docs` when `ENVIRONMENT != production`.

**Auth.** Register/login set an HTTP-only `acc_session` cookie (`SameSite=Lax`, `Secure` in production). API clients may instead send `Authorization: Bearer <access_token>` (returned by register/login). Every route below except `register`, `login`, `logout`, and `health` requires authentication and only returns the caller's own data (other users' resources return 404).

**Errors.** `{"detail": "message"}`; validation errors are `422` with `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` (submitted values are never echoed). Rate limits return `429` with `Retry-After`. Unexpected errors return `500 {"detail": "Internal server error", "request_id": "…"}`.

## Health

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | `{status, database, redis}`; unauthenticated |

## Authentication

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| POST | `/auth/register` | `{email, password (≥10 chars, letters + digits/symbols), display_name?}` | `201 {user, access_token, token_type}`, `409` if email exists |
| POST | `/auth/login` | `{email, password}` | `200 {user, access_token, token_type}`, `401` generic error |
| POST | `/auth/logout` | – | `204`; revokes the token and clears the cookie (works even if the session already expired) |
| GET | `/auth/me` | – | `{id, email, display_name, created_at}` |

## Providers

| Method | Path | Response |
| --- | --- | --- |
| GET | `/providers` | `[{slug, name, capabilities, models[{id,name,max_outputs_per_request,sizes,default_size,qualities}], supports_usage_api}]` |

## Accounts

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| GET | `/accounts` | – | list of accounts |
| POST | `/accounts` | `{provider, label, api_key}` | `201` account. The key is verified with the provider first; `400` if rejected |
| GET | `/accounts/{id}` | – | account |
| POST | `/accounts/{id}/test` | – | `{ok, message, account}` |
| DELETE | `/accounts/{id}` | – | `204`; removes credentials and usage rows, keeps job history |
| GET | `/accounts/{id}/usage` | – | usage summary for one account |

Account fields: `id, provider, provider_name, label, status (active|invalid|disabled), available, capabilities, models, credential_hint (last 4 chars), rate_limited_until, last_request_at, last_validated_at, last_error, last_error_at, limits, created_at`. **The API key is never returned.**

## Jobs

### `POST /jobs` → `202`

```json
{
  "type": "image_generation",
  "prompt": "A futuristic city at night",
  "number_of_outputs": 4,
  "provider": "auto",
  "model": "auto",
  "size": null,
  "quality": null
}
```

Response: `{"job_id": "…", "status": "queued"}`. Validation: prompt 1–4000 chars, `number_of_outputs` 1–10, provider/model must exist (or be `auto`), max 50 active jobs per user.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/jobs?status=&limit=&offset=` | `{items, total}`, newest first |
| GET | `/jobs/{id}` | job with `events` timeline and `outputs` |
| GET | `/jobs/{id}/outputs` | list of outputs |
| POST | `/jobs/{id}/cancel` | `409` unless queued/processing/retrying |
| POST | `/jobs/{id}/retry` | `409` unless failed/cancelled |

Job fields: `id, type, prompt, requested_provider, requested_model, provider_used, model_used, account_label, number_of_outputs, status (queued|processing|retrying|completed|failed|cancelled), attempts, error, events[{stage,at,message?}], next_retry_at, created_at, started_at, completed_at, outputs[]`.

## Gallery & outputs

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/gallery?q=&limit=&offset=` | `{items, total}`; each item has `url, prompt, provider, model, account_label, created_at, size_bytes, metadata` |
| GET | `/outputs/{id}/file[?download=true]` | image bytes (`nosniff`, restrictive CSP) |
| DELETE | `/outputs/{id}` | `204`; deletes the DB row and the stored file |
| POST | `/outputs/download` | `{ids: [≤50]}` → `application/zip` |
| POST | `/outputs/delete` | `{ids: [≤50]}` → `{deleted}` |

## Usage

| Method | Path | Response |
| --- | --- | --- |
| GET | `/usage` | `{requests, images, input_tokens, output_tokens, accounts[], daily[]}` |

`input_tokens`/`output_tokens` are `null` when no provider reported them. Each account entry includes `provider_usage: {available, message}` (`"Usage information unavailable for this provider."` when unsupported) and any provider-reported `rate_limits`.

## Audit

| Method | Path | Response |
| --- | --- | --- |
| GET | `/audit-logs?limit=` | the caller's recent actions (`auth.*`, `account.*`, `job.*`, `output.*`); never contains secrets |
