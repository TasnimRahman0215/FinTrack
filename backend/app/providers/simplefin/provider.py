"""SimpleFIN implementation of the Provider interface, registered in providers/registry.py."""

import datetime as dt
from urllib.parse import urlsplit

import httpx

from app.core.clock import utcnow
from app.providers.base import FetchResult, Provider, ProviderAccount
from app.providers.simplefin import client
from app.providers.simplefin.mapper import map_response

# SimpleFIN Bridge warns when one request spans more than 45 days and may start capping it,
# so longer ranges (e.g. the 90-day first sync) are fetched in windows and merged.
MAX_WINDOW = dt.timedelta(days=45)


def date_windows(
    start: dt.datetime, end: dt.datetime, size: dt.timedelta = MAX_WINDOW
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Split [start, end] into consecutive windows of at most `size`, oldest first."""
    windows = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + size, end)
        windows.append((cursor, nxt))
        cursor = nxt
    return windows or [(start, end)]


def merge_results(results: list[FetchResult]) -> FetchResult:
    """Merge window results (oldest first): newest balance wins, transactions are de-duplicated."""
    accounts: dict[str, ProviderAccount] = {}
    errors: list[str] = []
    for result in results:
        errors.extend(result.errors)
        for acc in result.accounts:
            existing = accounts.get(acc.provider_account_id)
            if existing is None:
                accounts[acc.provider_account_id] = acc
                continue
            seen = {t.provider_txn_id for t in existing.transactions}
            existing.transactions.extend(
                t for t in acc.transactions if t.provider_txn_id not in seen
            )
            existing.name = acc.name
            existing.org_name = acc.org_name
            existing.currency = acc.currency
            existing.balance_cents = acc.balance_cents
            existing.available_cents = acc.available_cents
            existing.balance_as_of = acc.balance_as_of
            existing.holdings = acc.holdings or existing.holdings
    return FetchResult(accounts=list(accounts.values()), errors=list(dict.fromkeys(errors)))


class SimpleFINProvider(Provider):
    name = "simplefin"

    # Tests inject an httpx client with a mock transport; production uses a fresh one per call.
    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client

    def connect(self, setup_payload: str) -> tuple[str, str]:
        access_url = client.claim_access_url(setup_payload, client=self._http)
        host = urlsplit(access_url).hostname or "SimpleFIN"
        return access_url, f"SimpleFIN ({host})"

    def fetch(
        self, credentials: str, start: dt.datetime | None, end: dt.datetime | None
    ) -> FetchResult:
        if start is None:
            return map_response(client.fetch_accounts(credentials, None, end, client=self._http))
        windows = date_windows(start, end or utcnow())
        return merge_results(
            [
                map_response(client.fetch_accounts(credentials, w_start, w_end, client=self._http))
                for w_start, w_end in windows
            ]
        )
