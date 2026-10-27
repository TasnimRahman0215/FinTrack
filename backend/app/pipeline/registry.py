"""The list of post-sync processors and the runner called by services/sync_service.py."""

import logging

from sqlalchemy.orm import Session

from app.pipeline.base import Processor

log = logging.getLogger(__name__)

# Ordered. Later phases add e.g. TransferDetector(), Categorizer().
PROCESSORS: list[Processor] = []


def run_pipeline(db: Session, household_id: int, new_transaction_ids: list[int]) -> list[str]:
    """Run every processor; a failing processor is logged and reported but never fails a sync."""
    errors: list[str] = []
    for processor in PROCESSORS:
        try:
            processor.run(db, household_id, new_transaction_ids)
        except Exception as exc:  # noqa: BLE001
            log.exception("Processor %s failed", processor.name)
            db.rollback()
            errors.append(f"{processor.name} failed: {exc}")
    return errors
