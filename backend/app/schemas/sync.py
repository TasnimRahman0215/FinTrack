"""Sync run responses for api/v1/sync.py and the Settings sync status."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class SyncRunOut(ORMModel):
    id: int
    connection_id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    accounts_seen: int
    txns_new: int
    txns_updated: int
    txns_removed: int
    errors: list[str]


class SyncSkipped(BaseModel):
    """A connection "Sync now" didn't start, and why (cooldown or already syncing)."""

    connection_id: int
    reason: str


class SyncStartOut(BaseModel):
    """ "Sync now" result. Syncs run in the background; poll /connections (`syncing`) to see
    when they finish."""

    started: list[int]
    skipped: list[SyncSkipped]
