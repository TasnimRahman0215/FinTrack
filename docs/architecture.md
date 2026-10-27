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
  `CORS_ORIGINS`, `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` on the backend.

## Data model

All money is integer cents.

| Table | Purpose |
|---|---|
| `users` | A person (email, display name, argon2 password hash) |
| `households` | The tenant. All financial data belongs to one household |
| `household_memberships` | user ↔ household with a role: `owner` / `contributor` / `reader` |
| `household_invites` | One-time invite links (table exists; used by the invites feature) |
| `sessions` | Server-side sessions. The cookie holds a random token; only its HMAC is stored |
| `connections` | A SimpleFIN access URL, Fernet-encrypted, plus sync status and last error |
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
`backend/app/core/scope.py` and is covered by `tests/test_scope.py`.

## Roles

| Action | owner | contributor | reader |
|---|:-:|:-:|:-:|
| See shared data and your own | ✓ | ✓ | ✓ |
| Manual accounts and transactions, edit accounts | ✓ | ✓ | |
| Connect SimpleFIN, sync | ✓ | ✓ | |
| Rename household (later: invite and remove members) | ✓ | | |

Only an account's owner (or the household owner) can change its owner or visibility.

## Sync

```text
scheduler (every 30 min: syncs connections not synced in SYNC_INTERVAL_HOURS)  or  "Sync now"
  → sync_service.sync_connection
      → SimpleFIN fetch: window = last sync − 14 days (first sync: 90 days),
        split into ≤45-day requests (SimpleFIN's recommended maximum)
      → upsert accounts and transactions (dedupe on provider IDs; user fields untouched)
      → delete pending transactions the bank no longer reports (they reappear posted, with new IDs)
      → balance snapshot for today
      → pipeline processors (none yet)
      → sync_runs row
```

- "Sync now" has a 15-minute cooldown per connection, to stay under SimpleFIN's ~24 requests/day.
- A lock prevents the scheduler and the button from syncing the same connection at once.
- A 403 from SimpleFIN marks the connection `reauth_required`, and the scheduler skips it.
- SimpleFIN usually provides only about 90 days of history at first; FinTrack keeps everything after that.
  Older history needs CSV import (planned).

## Security

- Passwords: argon2. Login and signup are rate-limited, and unknown emails take the same time as wrong passwords.
- Sessions: HttpOnly cookie, `SameSite=Lax`, and `Secure` when `COOKIE_SECURE=true`. Revocable server-side.
- CSRF: every write request must send `X-Requested-With` (browsers can't add it cross-site without CORS approval).
- SimpleFIN credentials are encrypted at rest with `ENCRYPTION_KEY`.
- `ALLOW_SIGNUP=false` closes signups after the first account.

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
