# FinTrack architecture

## Overview

```text
Phone / PC browser
   │  http(s)
   ▼
frontend container (nginx serving the React build)
   │  /api/*  (same origin, so session cookies work without CORS)
   ▼
backend container (FastAPI)
   ├─ /api/v1/*     REST API (interactive docs at /api/docs)
   ├─ scheduler     syncs each connection every SYNC_INTERVAL_HOURS
   └─ SQLite file in the fintrack-data volume (or Postgres via DATABASE_URL)
   │  outbound HTTPS only
   ▼
SimpleFIN Bridge ──► banks, cards, brokerages
```

- The **frontend** (React + Vite, plain JavaScript) and **backend** (Python, FastAPI, SQLAlchemy, Alembic)
  are independent projects with separate Dockerfiles and images.
- The frontend calls `VITE_API_BASE_URL` (default `/api`). In development the Vite dev server forwards
  `/api`; in Docker nginx does. To host them on different domains, set a full URL plus
  `CORS_ORIGINS`, `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` on the backend, and
  `CSP_CONNECT_SRC="'self' https://your-api"` on the frontend container.

## Data model

All money is integer cents.

| Table | Purpose |
|---|---|
| `users` | A person (email, display name, argon2 password hash) |
| `households` | The tenant. All financial data belongs to one household |
| `household_memberships` | user ↔ household with a role: `owner` / `contributor` / `reader` |
| `household_invites` | One-time invite links (table exists; used by the invites feature) |
| `sessions` | Server-side sessions. The cookie holds a random token; only its HMAC is stored |
| `connections` | A SimpleFIN access URL, Fernet-encrypted, plus sync status, last error and `sync_lock_until` (the cross-process sync lock) |
| `accounts` | Synced or manual. `owner_user_id` (NULL = joint), `visibility` (shared/private), `kind`, `is_hidden` |
| `balance_snapshots` | One balance per account per day (for net-worth history) |
| `transactions` | `source` (simplefin/manual/import), unique `(account_id, provider_txn_id)`, `raw_json` kept |
| `sync_runs` | History of every sync, with counts and provider errors |

## Scope (who sees what)

Every data endpoint takes `?scope=`:

| Scope | Accounts included |
|---|---|
| `me` | accounts I own (shared or private) + joint |
| `member:<id>` | that member's **shared** accounts + joint |
| `household` | every member's shared accounts + joint |

Private accounts appear only in their owner's `me` view. This rule lives only in
`backend/app/core/scope.py` and is covered by `tests/test_scope.py` and `tests/test_security.py`.

- A **joint** account has no owner *and* is shared; the API forces joint accounts to stay shared.
  An account whose owner's user row is deleted keeps `visibility=private` and is visible to nobody,
  so it can never turn into a joint account by accident.
- **Connections** can hold several members' accounts. What a viewer sees about a connection (its
  label, account count, last error) only covers accounts they may see, and sync history is shown only
  to whoever added the connection. Provider error messages often name an institution, so other
  members get a generic message instead.
- Newly synced accounts start **private** to whoever connected them; they choose what to share.

## Roles

| Action | owner | contributor | reader |
|---|:-:|:-:|:-:|
| See shared data and your own | ✓ | ✓ | ✓ |
| Edit your own and joint accounts, add manual accounts and transactions to them | ✓ | ✓ | |
| Edit other members' (shared) accounts and their manual transactions | ✓ | | |
| Connect SimpleFIN, "Sync now" | ✓ | ✓ | |
| Remove a connection you added (the household owner also: one whose adder has left) | ✓ | ✓ | |
| Rename household (later: invite and remove members) | ✓ | | |

Only an account's owner (or the household owner) can change its owner or visibility; for a joint
account that means only the household owner. These rules live in `account_service.permissions`,
and every account in the API carries `can_edit` / `can_reassign` so the UI never re-derives them.

## Sync

```text
scheduler (every 30 min: syncs connections not synced in SYNC_INTERVAL_HOURS)  or  "Sync now"
  → claim the connection: one atomic UPDATE of connections.sync_lock_until (+ cooldown check)
  → sync_service.run_claimed
      → SimpleFIN fetch: window = last sync − 14 days (first sync: 90 days),
        split into ≤45-day requests (SimpleFIN's recommended maximum)
      → upsert accounts and transactions (dedupe on provider IDs; user fields untouched;
        new accounts start private)
      → delete pending transactions the bank no longer reports (they reappear posted, with new IDs)
      → balance snapshot for today
      → pipeline processors (none yet)
      → sync_runs row, then release the claim
```

- "Sync now" has a 15-minute cooldown per connection, to stay under SimpleFIN's ~24 requests/day.
  It only claims the connections and returns `202`; the syncs run in the background and
  `GET /connections` reports `syncing` until they finish.
- The claim lives in the database, so the API, the optional worker and the CLI never sync the same
  connection at once, even as separate processes. A claim left by a crashed process expires after
  30 minutes.
- A 403 from SimpleFIN marks the connection `reauth_required`, and the scheduler skips it.
- SimpleFIN usually provides only about 90 days of history at first; FinTrack keeps everything after that.
  Older history needs CSV import (planned).

## Security

- Passwords: argon2. Unknown emails take the same time as wrong passwords.
- Login rate limits: 30 attempts per IP and 10 per (email, IP) every 5 minutes, plus 100 per email
  every 15 minutes. Keying the tight limit on (email, IP) means a stranger who knows your email can
  only lock themselves out. The client IP comes from `X-Forwarded-For`, which nginx overwrites with
  the real address and uvicorn only trusts from `FORWARDED_ALLOW_IPS` (private Docker ranges by
  default). Behind another proxy (Caddy, Tailscale serve...), every request looks like it comes from
  that proxy, so the per-IP limit becomes shared.
- Sessions: HttpOnly cookie, `SameSite=Lax`, and `Secure` when `COOKIE_SECURE=true`. Revocable server-side.
  Use HTTPS beyond localhost: over plain HTTP, passwords and cookies cross the network unencrypted.
- CSRF: every write request must send `X-Requested-With` (browsers can't add it cross-site without CORS approval).
- SimpleFIN credentials are encrypted at rest with `ENCRYPTION_KEY`. FinTrack only contacts hosts in
  `SIMPLEFIN_ALLOWED_HOSTS` (default `simplefin.org` and its subdomains, HTTPS on port 443), so a
  pasted token or access URL can't make the server call other addresses. Network error details go to
  the server log, not to users.
- The Docker image runs with `ENVIRONMENT=production`: it refuses to start without a real
  `SECRET_KEY` and doesn't serve `/api/docs`.
- nginx (unprivileged) sends a strict Content-Security-Policy, `X-Frame-Options: DENY`,
  `X-Content-Type-Options`, `Referrer-Policy` and `Permissions-Policy`. If the API is on another
  origin, add it to `CSP_CONNECT_SRC`.
- `ALLOW_SIGNUP=false` closes signups after the first account. While signups are open, anyone who
  can reach the server can create an account (in a separate household) and can find out whether an
  email is registered, so close them once your household has joined.

## Performance

A couple using cards heavily for three years generates roughly 15–30k transactions. A test inserts 50k
transactions and checks that the scoped list, a month filter, search and the summary all respond in
under 0.5 s on SQLite (`tests/test_migrations_and_perf.py`). Transactions use keyset pagination on
`(date, id)` with indexes on `(account_id, date)` and `(date)`.

## Roadmap

1. ~~Foundation: auth, households, SimpleFIN sync, scoped views, manual transactions~~
2. Family invites: invite link with a role, join on signup, member management
3. Categories: seeded categories, rules, categorizer and transfer-detection processors
4. Timeframes: date range picker (the API already accepts `start`/`end`)
5. Analytics: cash flow, spending by category, net-worth history (from `balance_snapshots`)
6. Investments: holdings (SimpleFIN returns them when the brokerage provides them)
7. CSV/OFX import, budgets, recurring detection, installable PWA, Tailscale/cloud deployment guide, CI publishing images to GHCR
