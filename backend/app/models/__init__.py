"""Database tables (SQLAlchemy models), one file per table.

Importing this package registers every table on Base.metadata (needed by Alembic). After changing
a model, create a migration: `alembic revision --autogenerate -m "..."` (see CONTRIBUTING.md).
"""

from app.models.account import Account
from app.models.balance_snapshot import BalanceSnapshot
from app.models.connection import Connection
from app.models.household import Household
from app.models.invite import HouseholdInvite
from app.models.membership import HouseholdMembership
from app.models.session import UserSession
from app.models.sync_run import SyncRun
from app.models.transaction import Transaction
from app.models.user import User

__all__ = [
    "Account",
    "BalanceSnapshot",
    "Connection",
    "Household",
    "HouseholdInvite",
    "HouseholdMembership",
    "SyncRun",
    "Transaction",
    "User",
    "UserSession",
]
