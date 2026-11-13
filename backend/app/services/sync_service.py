"""Sync orchestration: provider fetch -> upsert accounts/transactions -> balance snapshots ->
post-sync pipeline -> sync_runs record. Provider-agnostic: works with any `Provider`.

Called from four places: api/v1/connections.py (first sync after connecting), api/v1/sync.py
("Sync now"), jobs/sync_job.py (scheduled) and the `fintrack sync` CLI. See
docs/architecture.md#sync for the overview.

Concurrency: a connection is claimed with one atomic UPDATE on `connections.sync_lock_until`
(`try_claim`), so the API, the optional worker and the CLI never sync the same connection at once,
even in different processes. The same UPDATE enforces the minimum gap between syncs.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import AppError, ProviderAuthError
from app.models import Account, Connection, SyncRun, Transaction
from app.models.enums import ConnectionStatus, SyncStatus, Visibility
from app.pipeline.registry import run_pipeline
from app.providers.base import FetchResult, Provider, ProviderAccount, ProviderTransaction
from app.providers.registry import get_provider
from app.repositories import account_repo, balance_repo, connection_repo, transaction_repo
from app.schemas.sync import SyncSkipped, SyncStartOut
from app.services.account_service import guess_kind

log = logging.getLogger(__name__)

# A claim expires after this long, so a sync whose process died doesn't block the connection
# forever. Far longer than any real sync (a few HTTP calls with 60 s timeouts).
LOCK_TTL = timedelta(minutes=30)

# Provider fields refreshed on every sync. User fields (notes, ...) are never touched.
_TXN_PROVIDER_FIELDS = (
    "date",
    "posted_at",
    "transacted_at",
    "amount_cents",
    "description",
    "payee",
    "memo",
    "pending",
)


def try_claim(db: Session, connection: Connection, *, min_gap: timedelta | None = None) -> bool:
    """Atomically mark `connection` as syncing. False if it's already syncing (in any process)
    or, with `min_gap`, if the last attempt was less than `min_gap` ago.

    On success the cooldown clock (`last_attempt_at`) starts now and `connection` is refreshed.
    """
    now = utcnow()
    conditions = [
        Connection.id == connection.id,
        or_(Connection.sync_lock_until.is_(None), Connection.sync_lock_until < now),
    ]
    if min_gap is not None:
        conditions.append(
            or_(Connection.last_attempt_at.is_(None), Connection.last_attempt_at <= now - min_gap)
        )
    result = db.execute(
        update(Connection)
        .where(*conditions)
        .values(sync_lock_until=now + LOCK_TTL, last_attempt_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if result.rowcount != 1:
        return False
    db.refresh(connection)
    return True


def is_syncing(connection: Connection) -> bool:
    return connection.sync_lock_until is not None and connection.sync_lock_until > utcnow()


def sync_connection(
    db: Session,
    connection: Connection,
    *,
    trigger: str = "manual",
    provider: Provider | None = None,
    min_gap: timedelta | None = None,
) -> SyncRun | None:
    """Claim and sync one connection. None if it's already syncing (or synced within min_gap)."""
    if not try_claim(db, connection, min_gap=min_gap):
        return None
    return run_claimed(db, connection, trigger=trigger, provider=provider)


def run_claimed(
    db: Session, connection: Connection, *, trigger: str, provider: Provider | None = None
) -> SyncRun:
    """Sync a connection already claimed with `try_claim`, then release the claim."""
    try:
        return _sync_locked(db, connection, trigger, provider or get_provider(connection.provider))
    finally:
        db.rollback()  # drop anything a failure left half-done before releasing
        connection.sync_lock_until = None
        db.commit()


def _sync_locked(db: Session, connection: Connection, trigger: str, provider: Provider) -> SyncRun:
    settings = get_settings()
    # Re-fetch a little before the last sync: pending items post later and can change amount/date.
    now = utcnow()
    earliest = now - timedelta(days=settings.initial_sync_days)
    start = (
        max(connection.last_synced_at - timedelta(days=settings.sync_overlap_days), earliest)
        if connection.last_synced_at
        else earliest
    )

    # Record the run up front so it shows as "running" (try_claim already started the cooldown).
    run = SyncRun(connection_id=connection.id, trigger=trigger, errors=[])
    db.add(run)
    db.commit()

    try:
        result = provider.fetch(security.decrypt(connection.credentials_enc), start, now)
    except ProviderAuthError as exc:
        return _fail(db, connection, run, exc.message, ConnectionStatus.REAUTH_REQUIRED)
    except AppError as exc:
        return _fail(db, connection, run, exc.message, ConnectionStatus.ERROR)
    # Raw exception text can include SQL parameters or provider data, and last_error is shown to
    # every household member, so the details only go to the server log.
    except Exception:  # noqa: BLE001
        log.exception("Sync of connection %s failed", connection.id)
        return _fail(
            db, connection, run, "Unexpected error; see the server log.", ConnectionStatus.ERROR
        )

    try:
        new_ids = _apply(db, connection, run, result, start)
    except Exception:  # noqa: BLE001
        log.exception("Saving sync results for connection %s failed", connection.id)
        return _fail(
            db,
            connection,
            run,
            "Couldn't save synced data; see the server log.",
            ConnectionStatus.ERROR,
        )

    connection.status = ConnectionStatus.ACTIVE
    connection.last_synced_at = now
    connection.last_error = "; ".join(result.errors) or None
    run.errors = list(result.errors)
    db.commit()  # persist synced data before processors run

    pipeline_errors = run_pipeline(db, connection.household_id, new_ids)
    run.errors = [*run.errors, *pipeline_errors]
    run.status = SyncStatus.PARTIAL if run.errors else SyncStatus.SUCCESS
    run.finished_at = utcnow()
    db.commit()
    log.info(
        "Synced connection %s: %s accounts, %s new, %s updated, %s removed",
        connection.id,
        run.accounts_seen,
        run.txns_new,
        run.txns_updated,
        run.txns_removed,
    )
    return run


def _apply(
    db: Session, connection: Connection, run: SyncRun, result: FetchResult, start: datetime
) -> list[int]:
    """Upsert accounts and transactions from `result`. Returns the IDs of new transactions."""
    existing = account_repo.by_provider_ids(db, connection.id)
    new_txns: list[Transaction] = []

    for p_account in result.accounts:
        account = existing.get(p_account.provider_account_id)
        if account is None:
            account = _create_account(db, connection, p_account)
        _update_account(account, p_account)
        balance_repo.upsert_snapshot(
            db,
            account_id=account.id,
            date=(account.balance_as_of or utcnow()).date(),
            balance_cents=account.balance_cents,
        )

        found = transaction_repo.existing_by_provider_ids(
            db, account.id, [t.provider_txn_id for t in p_account.transactions]
        )
        for p_txn in p_account.transactions:
            txn = found.get(p_txn.provider_txn_id)
            if txn is None:
                txn = _new_transaction(account.id, connection.provider, p_txn)
                db.add(txn)
                new_txns.append(txn)
                found[p_txn.provider_txn_id] = txn
            elif _update_transaction(txn, p_txn):
                run.txns_updated += 1

        run.txns_removed += transaction_repo.delete_stale_pending(
            db,
            account_id=account.id,
            since=start.date(),
            keep_provider_ids={t.provider_txn_id for t in p_account.transactions},
        )
        run.accounts_seen += 1

    db.flush()
    run.txns_new = len(new_txns)
    # The connection's label isn't overwritten with institution names: that would reveal members'
    # private accounts. connection_service builds a per-viewer label instead.
    return [t.id for t in new_txns]


def _create_account(db: Session, connection: Connection, p: ProviderAccount) -> Account:
    """First time we see an account: guess its kind and give it to whoever connected it.

    New accounts start PRIVATE: the person who connected them decides what the household sees,
    instead of everything being visible until they notice and hide it.
    """
    return account_repo.add(
        db,
        Account(
            household_id=connection.household_id,
            source=connection.provider,  # the provider name is also its Source value
            connection_id=connection.id,
            provider_account_id=p.provider_account_id,
            name=p.name,
            kind=guess_kind(p.name, p.org_name, p.balance_cents),
            owner_user_id=connection.added_by_user_id,  # whoever connected it; editable later
            visibility=Visibility.PRIVATE,
        ),
    )


def _update_account(account: Account, p: ProviderAccount) -> None:
    """Refresh provider fields only; user fields (display_name, owner, ...) are left alone."""
    account.name = p.name
    account.org_name = p.org_name
    account.currency = p.currency
    account.balance_cents = p.balance_cents
    account.available_cents = p.available_cents
    account.balance_as_of = p.balance_as_of or utcnow()


def _new_transaction(account_id: int, source: str, p: ProviderTransaction) -> Transaction:
    return Transaction(
        account_id=account_id,
        source=source,
        provider_txn_id=p.provider_txn_id,
        date=p.date,
        posted_at=p.posted_at,
        transacted_at=p.transacted_at,
        amount_cents=p.amount_cents,
        description=p.description,
        payee=p.payee,
        memo=p.memo,
        pending=p.pending,
        raw_json=p.raw,
    )


def _update_transaction(txn: Transaction, p: ProviderTransaction) -> bool:
    """Refresh provider fields; returns True if anything changed."""
    changed = False
    for field in _TXN_PROVIDER_FIELDS:
        value = getattr(p, field)
        if getattr(txn, field) != value:
            setattr(txn, field, value)
            changed = True
    if changed:
        txn.raw_json = p.raw
    return changed


def _fail(
    db: Session, connection: Connection, run: SyncRun, message: str, status: ConnectionStatus
) -> SyncRun:
    """Discard partial changes and record the failure on the run and the connection."""
    db.rollback()
    connection.status = status
    connection.last_error = message
    run.status = SyncStatus.FAILED
    run.errors = [message]
    run.finished_at = utcnow()
    db.commit()
    return run


def start_household_sync(db: Session, household_id: int) -> SyncStartOut:
    """'Sync now': claim every connection in a household that isn't syncing or in its cooldown
    (which keeps us under SimpleFIN's ~24 requests/day/connection). The caller runs the claimed
    ones with `run_claimed` in the background, so the request returns at once."""
    cooldown = timedelta(minutes=get_settings().sync_cooldown_minutes)
    started: list[int] = []
    skipped: list[SyncSkipped] = []
    for connection, _ in connection_repo.list_for_household(db, household_id):
        if try_claim(db, connection, min_gap=cooldown):
            started.append(connection.id)
            continue
        db.refresh(connection)
        if is_syncing(connection):
            reason = "Already syncing."
        else:
            since = utcnow() - (connection.last_attempt_at or utcnow())
            wait = max(int((cooldown - since).total_seconds() // 60) + 1, 1)
            reason = f"Synced recently; try again in {wait} min."
        skipped.append(SyncSkipped(connection_id=connection.id, reason=reason))
    return SyncStartOut(started=started, skipped=skipped)


def sync_due(db: Session) -> int:
    """Scheduler entry point: sync every connection last attempted longer ago than the interval."""
    # 5-minute slack so a connection isn't skipped just because the check ran slightly early.
    due_after = timedelta(hours=get_settings().sync_interval_hours) - timedelta(minutes=5)
    count = 0
    for connection in connection_repo.list_all(db):
        if connection.status == ConnectionStatus.REAUTH_REQUIRED:
            continue
        if sync_connection(db, connection, trigger="scheduled", min_gap=due_after):
            count += 1
    return count
