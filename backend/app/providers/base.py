"""The provider interface. Every data source (SimpleFIN, CSV import, ...) produces these
normalized objects, so the sync service never needs to know where the data came from.

Money is integer cents; datetimes are naive UTC. services/sync_service.py consumes these.
"""

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderTransaction:
    """One transaction. `provider_txn_id` must be stable so re-syncs update instead of duplicate."""

    provider_txn_id: str
    date: dt.date
    amount_cents: int
    description: str
    posted_at: dt.datetime | None = None
    transacted_at: dt.datetime | None = None
    payee: str | None = None
    memo: str | None = None
    pending: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHolding:
    """One investment position (parsed now, stored once the investments feature lands)."""

    provider_holding_id: str
    symbol: str | None
    description: str | None
    shares: str | None  # kept as decimal strings; stored once the holdings feature lands
    market_value_cents: int | None
    cost_basis_cents: int | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderAccount:
    """One account with its current balance and the transactions in the requested range."""

    provider_account_id: str
    name: str
    org_name: str | None
    currency: str
    balance_cents: int
    available_cents: int | None
    balance_as_of: dt.datetime | None
    transactions: list[ProviderTransaction] = field(default_factory=list)
    holdings: list[ProviderHolding] = field(default_factory=list)


@dataclass
class FetchResult:
    """Everything one fetch returned."""

    accounts: list[ProviderAccount]
    errors: list[str] = field(default_factory=list)  # non-fatal, e.g. "Robinhood needs re-auth"


class Provider(ABC):
    """Interface every data source implements. `name` is stored on each connection."""

    name: str

    @abstractmethod
    def connect(self, setup_payload: str) -> tuple[str, str]:
        """Exchange what the user pasted for long-lived credentials.

        Returns (credentials, label). Credentials are encrypted before they're stored.
        """

    @abstractmethod
    def fetch(
        self, credentials: str, start: dt.datetime | None, end: dt.datetime | None
    ) -> FetchResult:
        """Return accounts with balances and transactions in [start, end] (naive UTC)."""
