# Contributing to FinTrack

Thanks for helping! The README covers setup. This file explains how the code is organised
and how to add a feature without fighting it.

## Ground rules

- **Money is integer cents** everywhere (`amount_cents`, `balance_cents`). Never floats.
- **Datetimes are naive UTC** in the database (`app/core/clock.py`).
- **Privacy is decided in one place:** `backend/app/core/scope.py`. Every endpoint that returns
  financial data must take the `get_scope` dependency and filter by `scope.account_ids`.
- **Writes need a role:** use `Depends(require_role(Role.CONTRIBUTOR))` (or `OWNER`).
- **Sync never overwrites user fields.** Provider columns (name, balance, description...) are refreshed;
  user columns (display_name, kind, owner, visibility, notes...) are not.
- **Schema changes go through Alembic.** People run this on their own data, so never edit an existing migration.

## Backend layers (`backend/app`)

| Layer | Folder | Does |
|---|---|---|
| Router | `api/v1/*.py` | HTTP only: parse input, call a service, return a schema |
| Schema | `schemas/` | Pydantic request/response models (the API contract) |
| Service | `services/` | Business rules and permission checks; **owns `db.commit()`** |
| Repository | `repositories/` | SQLAlchemy queries; flush but never commit |
| Model | `models/` | Tables |
| Provider | `providers/` | Data sources (SimpleFIN). Return provider-neutral objects |
| Pipeline | `pipeline/` | Processors that run after every sync (categorizer, transfer detection...) |

## Recipe: adding a feature (example: categories)

1. **Model**: `models/category.py`, export it from `models/__init__.py`.
2. **Migration**: `alembic revision --autogenerate -m "add categories"`. Review the generated file.
3. **Repository**: `repositories/category_repo.py`.
4. **Service**: `services/category_service.py`.
5. **Schemas + router**: `schemas/category.py`, `api/v1/categories.py` (use `get_scope` / `require_role`),
   then register it in `api/v1/router.py`.
6. **Optional processor**: `pipeline/categorizer.py`, added to `PROCESSORS` in `pipeline/registry.py`.
7. **Tests**: `tests/test_categories.py`.
8. **Frontend**: `src/api/categories.js` → `src/features/categories/` (page, components, query hooks
   whose keys include the scope) → a route in `src/App.jsx` → a nav item in `components/layout/nav.js`.

## Adding a data source

Implement `Provider` in `providers/<name>/` (`connect()` and `fetch()` returning `FetchResult`), then
register it in `providers/registry.py`. The sync service, scope rules and UI work unchanged.

## Frontend (`frontend/src`)

- `api/`: the only code that knows URLs. `client.js` adds the CSRF header, cookies and error handling.
- `context/`: `AuthContext` (current user and role) and `ScopeContext` (Me / member / Household).
- `features/<feature>/`: pages, components and TanStack Query hooks for one feature.
- `components/ui/`: small shared building blocks (Button, Card, Dialog, Form fields...).
- `lib/`: formatting (money, dates), labels, query keys.
