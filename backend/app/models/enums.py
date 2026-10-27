"""Allowed values for string columns.

Stored as plain strings, so adding a value needs no migration.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    CONTRIBUTOR = "contributor"
    READER = "reader"


# Higher rank includes everything a lower rank can do (used by require_role in api/deps.py).
ROLE_RANK = {Role.READER: 0, Role.CONTRIBUTOR: 1, Role.OWNER: 2}


class AccountKind(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"
    INVESTMENT = "investment"
    LOAN = "loan"
    OTHER = "other"


class Visibility(StrEnum):
    SHARED = "shared"  # visible in the household view and to other members
    PRIVATE = "private"  # visible only to the account's owner


class Source(StrEnum):
    """Where an account or transaction came from."""

    SIMPLEFIN = "simplefin"
    MANUAL = "manual"
    IMPORT = "import"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    ERROR = "error"
    REAUTH_REQUIRED = "reauth_required"


class SyncStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"  # finished, but the provider reported errors for some accounts
    FAILED = "failed"
