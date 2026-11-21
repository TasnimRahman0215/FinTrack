"""Time helpers. All datetimes are stored as naive UTC so SQLite and Postgres behave the same.

Use `utcnow()` instead of `datetime.now()` anywhere a timestamp is saved or compared.
"""

from datetime import UTC, date, datetime


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utctoday() -> date:
    return utcnow().date()


def to_unix(value: datetime) -> int:
    """Convert a naive-UTC datetime to a unix timestamp."""
    return int(value.replace(tzinfo=UTC).timestamp())


def from_unix(value: int | str | None) -> datetime | None:
    """Parse a unix timestamp (as SimpleFIN sends them); empty or 0 means "no value"."""
    if value in (None, "", 0, "0"):
        return None
    return datetime.fromtimestamp(int(value), UTC).replace(tzinfo=None)
