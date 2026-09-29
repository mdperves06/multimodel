# Security

## Principles

- **Official APIs only.** No stolen credentials, browser cookies, session-token extraction, CAPTCHA/anti-bot bypass, hidden browser automation, or scraping of private sessions. Users are never asked for website passwords.
- **Respect provider limits.** HTTP 429 blocks the account for the provider's own retry window; the app never rotates keys or retries early to evade a limit.

## Controls

| Area | Implementation |
| --- | --- |
| Passwords | Argon2id (`argon2-cffi`), min 10 chars mixing letters with digits/symbols; constant-time-ish login (dummy hash for unknown emails) and one generic error message |
| Sessions | Per-user token version lets "sign out everywhere" and password changes revoke all sessions at once. JWT (HS256, `exp`/`sub`/`jti` required) in an `HttpOnly`, `SameSite=Lax`, `Secure`(prod) cookie. Logout revokes the `jti` in Redis until expiry; if Redis is unreachable, token validation fails closed |
| Provider credentials | Verified with the provider, then encrypted with Fernet (AES-128-CBC + HMAC) using `ENCRYPTION_KEY` before insertion. Only the last 4 characters are kept for display. No API returns the key; audit logs and errors never contain it |
| Authorization | Every private route requires auth and filters by `user_id`; other users' objects return 404 (covered by tests for accounts, jobs, outputs, bulk operations) |
| Input validation | Pydantic constraints on every body/query (lengths, ranges, regexes, enums); SQLAlchemy parameter binding everywhere; `LIKE` wildcards escaped in gallery search |
| Rate limiting | Redis fixed-window per IP: global 300/min; auth endpoints 10/min; job creation 60/min; account connection 20/min; plus 10 login attempts/min per email across IPs. Falls back to per-process counters if Redis is down. Per-user cap of 50 active jobs |
| CSRF | `SameSite=Lax` cookie, JSON-only API, and an `Origin` allow-list check on every state-changing request |
| HTTP headers | API: `nosniff`, `X-Frame-Options: DENY`, strict CSP (`default-src 'none'`), `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, HSTS (prod). Frontend: CSP (same-origin only, `frame-ancestors 'none'`), `nosniff`, frame denial, HSTS (prod) |
| XSS | React escapes all user content (prompts rendered as text); images are served with an allow-listed image MIME type, `nosniff`, and a restrictive CSP |
| Request limits | JSON body ≤ 1 MB (413), bulk operations ≤ 50 ids, `TrustedHost` allow-list (`ALLOWED_HOSTS`) |
| Error handling | Unhandled errors return a generic 500 with a request id; validation errors omit submitted values |
| Logging | Formatter redacts `sk-…` keys, bearer tokens, JWTs, and `password/api_key/secret/token` assignments, including in tracebacks |
| Audit | `audit_logs` records auth events, account connect/test/disconnect, job create/cancel/retry, output deletes (user, IP, metadata without secrets) |
| Configuration | The app refuses to start without a ≥32-char `JWT_SECRET` and a valid `ENCRYPTION_KEY`; in production it also rejects SQLite, in-memory Redis, and the mock provider; OpenAPI docs are disabled in production |
| Containers | Non-root users, health checks, Postgres/Redis not exposed publicly in the production override |
| Supply chain | `pip-audit` and `npm audit` run in CI; dependencies are pinned by lockfile (frontend) |

## Operational guidance

- **Back up `ENCRYPTION_KEY`.** Rotating it invalidates stored credentials until users reconnect their accounts (a re-encryption tool is not included).
- Keep `.env` out of git (`.gitignore` covers it), and use your platform's secret manager in production.
- Terminate TLS in front of the app; otherwise `Secure` cookies will not be sent.
- Set `TRUST_PROXY=true` only when a trusted proxy overwrites `X-Forwarded-For`, otherwise clients can spoof IPs and dodge IP rate limits.
- Restrict who can read the Postgres volume, the storage volume, and Redis (it holds token revocations and queue contents).
- Use least-privilege API keys with billing limits at the provider.

## Known limitations / not implemented

- No email verification, forgotten-password reset, or MFA (these need an outbound email service, which is deployment-specific).
- Registration reveals whether an email exists (409). Login does not.
- Sessions last 12 hours. Single sessions are revoked on logout; "sign out of all devices" and password changes invalidate every session through a per-user token version.
- Uploaded/generated images are not scanned; they come only from the configured provider.
- The frontend CSP needs `'unsafe-inline'` scripts because of Next.js hydration; moving to nonces is a future improvement.
- Local disk storage has no server-side encryption; use an encrypted volume, or enable server-side encryption on your S3/R2 bucket.

## Reporting

Open a private security advisory on the GitHub repository rather than a public issue.
