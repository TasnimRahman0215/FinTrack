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
| `security_events` | Sign-ins, failed sign-ins, password and access changes: IDs, IP and browser only, kept a year |

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
| Everything on your own accounts | ✓ | ✓ | |
| Everyday edits on joint accounts (name, type, manual transactions) | ✓ | ✓ | |
| Give a joint account an owner, make it private, hide it, delete it | ✓ | | |
| Look after a former member's accounts (edit, reassign, delete) | ✓ | | |
| Change another current member's account in any way | | | |
| Connect SimpleFIN, "Sync now" | ✓ | ✓ | |
| Remove a connection you added (the household owner: one whose adder left or is now a reader) | ✓ | ✓ | |
| Rename household (later: invite and remove members) | ✓ | | |

An account belongs to its owner: not even the household owner can edit, reassign, hide or delete
another current member's account. Joint accounts belong to everyone, so contributors make everyday
edits, but only the household owner can take one away from the household (owner, visibility,
hidden, delete). These rules live in `account_service.permissions`, and every account in the API
carries `can_edit` / `can_manage` so the UI never re-derives them.

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

- "Sync now" has a 15-minute cooldown and a daily cap (`SYNC_MANUAL_DAILY_LIMIT`, default 12) per
  connection. With the 4 scheduled syncs a day that stays under SimpleFIN's ~24 requests/day.
  It only claims the connections and returns `202`; the syncs run in the background and
  `GET /connections` reports `syncing` until they finish.
- The claim lives in the database, so the API, the optional worker and the CLI never sync the same
  connection at once, even as separate processes. A claim left by a crashed process expires after
  30 minutes.
- A 403 from SimpleFIN marks the connection `reauth_required`, and the scheduler skips it.
- SimpleFIN usually provides only about 90 days of history at first; FinTrack keeps everything after that.
  Older history needs CSV import (planned).

## Security

- Passwords: argon2. Unknown emails take the same time as wrong passwords. Each hash needs ~64 MiB,
  so at most `PASSWORD_HASH_CONCURRENCY` (default 2) run at once; others wait (a 503 after 10 s).
  Without the cap, 30 parallel logins took the API from 80 MiB to ~1 GB; with it, ~220 MiB.
- Accounts: users change their password in Settings (other sessions are signed out) and can sign out
  everywhere. An admin can reset a forgotten password with `fintrack reset-password <email>`.
- Login rate limits: 30 attempts per IP and 10 per (email, IP) every 5 minutes, plus 100 per email
  every 15 minutes. Keying the tight limit on (email, IP) means a stranger who knows your email can
  only lock themselves out. The client IP comes from `X-Forwarded-For`, which nginx overwrites with
  the real address and uvicorn only trusts from `FORWARDED_ALLOW_IPS` (private Docker ranges by
  default). Behind another reverse proxy (Caddy, Tailscale serve, a load balancer), set
  `TRUSTED_PROXIES` on the frontend container to that proxy's address: nginx then takes the real
  client IP from the proxy's `X-Forwarded-For`, and ignores the header from anyone else. Without
  it, every user behind the proxy shares one IP and one limit.
- Sessions: HttpOnly cookie, `SameSite=Lax`, revocable server-side. Idle sessions end after
  `SESSION_DAYS` (30) and every session after `SESSION_MAX_DAYS` (90), however active.
  Use HTTPS beyond localhost (`COOKIE_SECURE=true`): over plain HTTP, passwords and cookies cross the
  network unencrypted. Over HTTPS the cookie is named `__Host-fintrack_session`, which binds it to
  exactly this host.
- **Give FinTrack its own hostname** (e.g. `fintrack.home.lan` or its own Tailscale machine name).
  Browsers send cookies to every port of a host, so another app at `myserver:8080` would receive
  FinTrack's session cookie if FinTrack runs at `myserver:3000`.
- API responses carry `Cache-Control: no-store`, so financial data isn't kept in browser caches.
- CSRF: every write request must send `X-Requested-With` (browsers can't add it cross-site without CORS approval).
  `CORS_ORIGINS` must list exact origins; `*` is refused at startup, because with credentials
  allowed it would let any website use a signed-in user's session.
- SimpleFIN credentials are encrypted at rest with `ENCRYPTION_KEY`. FinTrack only contacts hosts in
  `SIMPLEFIN_ALLOWED_HOSTS` (default `simplefin.org` and its subdomains, HTTPS on port 443), so a
  pasted token or access URL can't make the server call other addresses. Network error details go to
  the server log, not to users.
- The Docker image runs with `ENVIRONMENT=production`: it refuses to start unless `SECRET_KEY` is set
  and at least 32 characters, and it doesn't serve `/api/docs`.
- SimpleFIN URLs are parsed with the same library (httpx) that sends the request, so the host that
  is checked is the host that is contacted; anything it can't parse is a 400, not a crash.
- nginx (unprivileged) sends a strict Content-Security-Policy, `X-Frame-Options: DENY`,
  `X-Content-Type-Options`, `Referrer-Policy` and `Permissions-Policy`. If the API is on another
  origin, add it to `CSP_CONNECT_SRC`.
- **Data at rest.** The database holds every transaction unencrypted, so:
  - run FinTrack on an encrypted disk (FileVault on macOS, LUKS on Linux). This is required, not
    optional, for a server holding a household's finances;
  - the database, its `-wal`/`-shm` files and backups are created owner-only (`0600`, new folders
    `0700`; the container also runs with `umask 077`), and older world-readable files are
    tightened at startup;
  - `fintrack backup` encrypts with `ENCRYPTION_KEY` by default (Fernet: AES + HMAC, so a modified
    backup is refused); the unencrypted snapshot only exists in memory. `fintrack restore-backup`
    decrypts and integrity-checks it. `--plaintext` is only for tools that encrypt themselves
    (e.g. restic). Keep `ENCRYPTION_KEY` somewhere other than the backups.
- **Logs never contain financial data.** The database engine uses `hide_parameters`, so errors
  show SQL but not values; sync errors log only connection IDs.
- **Security event log.** Sign-ins, failed sign-ins (also for unknown emails, without the email, so
  timing reveals nothing), sign-outs, password changes and resets, bank connections added or
  removed, account owner/visibility/hidden changes, account deletions and household renames are
  stored in `security_events` and written as JSON lines to the `fintrack.audit` logger. Each user
  sees their own recent activity in Settings. Rate-limit hits are logged only, so a flood of
  requests can't fill the database.
- **Error responses** say which field failed and why, but never echo the submitted value
  (passwords, tokens). IDs outside the database's integer range are rejected with a 4xx.
- **Containers** run read-only with all Linux capabilities dropped and `no-new-privileges`; only
  the data volume and small `tmpfs` areas are writable. The backend runs as an unprivileged user,
  nginx as the unprivileged `nginx` user.
- **Network.** The web app listens on `127.0.0.1` only by default, since it speaks plain HTTP. Use
  HTTPS (Tailscale serve, Caddy) to reach it from other devices. `FRONTEND_BIND=0.0.0.0` exposes
  plain HTTP to your whole network and is not advised.
- **Supply chain.** Base images are pinned by digest; `uv.lock` and `package-lock.json` pin every
  dependency with hashes. Dependabot (`.github/dependabot.yml`) proposes updates weekly and for
  security advisories.
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
