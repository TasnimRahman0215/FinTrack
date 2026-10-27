"""Convert SimpleFIN JSON into the provider-neutral objects in providers/base.py.

SimpleFIN sends money as decimal strings ("-45.67") and dates as unix timestamps. The format is
documented at https://www.simplefin.org/protocol.html; tests/fixtures/simplefin_accounts.json
is a sample.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.core.clock import from_unix, utcnow
from app.providers.base import (
    FetchResult,
    ProviderAccount,
    ProviderHolding,
    ProviderTransaction,
)


def to_cents(value: Any) -> int | None:
    """Convert "12.345" to 1235. Uses Decimal so amounts never pick up float rounding errors."""
    if value in (None, ""):
        return None
    try:
        return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None


def _str_or_none(value: Any, limit: int) -> str | None:
    """Empty -> None; otherwise a string trimmed to fit its database column."""
    if value in (None, ""):
        return None
    return str(value)[:limit]


def map_transaction(raw: dict[str, Any]) -> ProviderTransaction:
    posted_at = from_unix(raw.get("posted"))
    transacted_at = from_unix(raw.get("transacted_at"))
    # Show the purchase date when the bank provides it; pending items have posted = 0.
    when = transacted_at or posted_at or utcnow()
    return ProviderTransaction(
        provider_txn_id=str(raw["id"]),
        date=when.date(),
        amount_cents=to_cents(raw.get("amount")) or 0,
        description=str(raw.get("description") or "")[:500],
        posted_at=posted_at,
        transacted_at=transacted_at,
        payee=_str_or_none(raw.get("payee"), 255),
        memo=_str_or_none(raw.get("memo"), 500),
        pending=bool(raw.get("pending")) or posted_at is None,
        raw=raw,
    )


def map_holding(raw: dict[str, Any]) -> ProviderHolding:
    return ProviderHolding(
        provider_holding_id=str(raw.get("id", "")),
        symbol=_str_or_none(raw.get("symbol"), 32),
        description=_str_or_none(raw.get("description"), 255),
        shares=_str_or_none(raw.get("shares"), 64),
        market_value_cents=to_cents(raw.get("market_value")),
        cost_basis_cents=to_cents(raw.get("cost_basis")),
        raw=raw,
    )


def map_account(raw: dict[str, Any]) -> ProviderAccount:
    org = raw.get("org") or {}
    return ProviderAccount(
        provider_account_id=str(raw["id"]),
        name=str(raw.get("name") or "Account")[:200],
        org_name=_str_or_none(org.get("name") or org.get("domain"), 200),
        currency=str(raw.get("currency") or "USD")[:16],
        balance_cents=to_cents(raw.get("balance")) or 0,
        available_cents=to_cents(raw.get("available-balance")),
        balance_as_of=from_unix(raw.get("balance-date")),
        transactions=[map_transaction(t) for t in raw.get("transactions") or []],
        holdings=[map_holding(h) for h in raw.get("holdings") or []],
    )


def map_response(data: dict[str, Any]) -> FetchResult:
    """Map a whole /accounts response. Account-level problems arrive as non-fatal `errors`."""
    errors: list[str] = [str(e) for e in data.get("errors") or []]
    # Newer protocol versions also send structured errors.
    for item in data.get("errlist") or []:
        msg = item.get("msg") if isinstance(item, dict) else str(item)
        if msg:
            errors.append(str(msg))
    return FetchResult(
        accounts=[map_account(a) for a in data.get("accounts") or []],
        errors=list(dict.fromkeys(errors)),  # de-duplicate, keeping order
    )
