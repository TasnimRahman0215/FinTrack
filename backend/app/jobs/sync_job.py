"""The scheduled job: sync every connection whose last sync is older than SYNC_INTERVAL_HOURS."""

import logging

from app.db.session import SessionLocal, get_engine
from app.services import sync_service

log = logging.getLogger(__name__)


def run_due_syncs() -> None:
    """Runs on the scheduler thread, so it opens its own DB session."""
    get_engine()
    with SessionLocal() as db:
        try:
            synced = sync_service.sync_due(db)
            if synced:
                log.info("Scheduled sync finished for %s connection(s)", synced)
        except Exception:  # noqa: BLE001 - never let the scheduler thread die
            log.exception("Scheduled sync failed")
