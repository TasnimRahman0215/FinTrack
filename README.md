# FinTrack

A simple, self-hosted personal finance tracker for a household.
Connect bank, credit card and brokerage accounts through [SimpleFIN Bridge](https://beta-bridge.simplefin.org),
then see **your own** finances, **another member's** shared finances, or the **whole household** together.

- Runs anywhere Docker runs (home server, Raspberry Pi, a free cloud VM); your data stays on your machine
- Works on phone and desktop in the browser
- Read-only: FinTrack can never move money
- The only cost is SimpleFIN Bridge ($15/year)

## Status

Phase 1 (foundation) is done:

- Sign up and log in from the web UI. Each signup creates a household with that person as owner.
- SimpleFIN connections with automatic background sync (every 6 hours) and a "Sync now" button
- Accounts grouped by type. Each account has an owner (a person or joint), a visibility (shared or private), and can be hidden.
- Manual accounts (cash, Venmo...) and manual transactions
- Dashboard: net worth, assets vs liabilities, breakdown by person and by account type, recent transactions
- Transactions list with search, account filter and infinite scroll
- A **Me / member / Household** switcher on every page

Next up: family invites (reader/contributor), categories, date ranges, charts, investments,
and CSV import. See [docs/architecture.md](docs/architecture.md#roadmap).

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
docker compose run --rm backend fintrack gen-keys   # paste both lines into backend/.env
docker compose up -d --build
```

Open <http://localhost:3000>, create your account, then go to **Settings → Add SimpleFIN connection**.

- Data lives in the `fintrack-data` Docker volume (SQLite). Back up `ENCRYPTION_KEY` too: without it,
  saved connections can't be decrypted.
- Once everyone in your household has signed up, set `ALLOW_SIGNUP=false` in `backend/.env`.
- `SECRET_KEY` and `ENCRYPTION_KEY` are **not** from SimpleFIN. FinTrack generates them (`fintrack gen-keys`).
  The only SimpleFIN value is the **setup token**, and you paste that into the app's UI, not into `.env`.
- To get a real setup token, open <https://bridge.simplefin.org/simplefin/create>.
- To try it without a real bank, paste the demo setup token from
  <https://beta-bridge.simplefin.org/info/developers>. Each demo token works once; reload that page for a new one.
  The demo access URL `https://demo:demo@beta-bridge.simplefin.org/simplefin` also works and can be reused.

## Local development (no Docker)

Requirements: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 20.19+.

```bash
# Backend: http://localhost:8000 (API docs at /api/docs)
cd backend
uv venv .venv && source .venv/bin/activate
uv sync --active                  # installs everything into backend/.venv
cp .env.example .env              # then: fintrack gen-keys, and paste the keys into .env
alembic upgrade head
uvicorn app.main:app --reload

# Frontend: http://localhost:5173 (forwards /api to the backend)
cd frontend
npm install
npm run dev
```

The Vite dev server listens on your network too, so you can open `http://<your-computer-ip>:5173` on your phone.

Tests and lint:

```bash
cd backend && pytest && ruff check . && ruff format --check .
cd frontend && npm run lint && npm run build
```

## How it fits together

```text
Browser ──► frontend (nginx / Vite) ──/api──► backend (FastAPI) ──► SQLite or Postgres
                                                    │
                                                    └─► SimpleFIN Bridge ──► your banks
```

The frontend and backend are independent projects with separate Docker images. They only share the
`/api/v1` HTTP contract. Details are in [docs/architecture.md](docs/architecture.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) explains how to add a feature.

## License

MIT
