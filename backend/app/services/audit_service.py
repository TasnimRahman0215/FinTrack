"""Security event log: sign-ins, password changes, connection and account-access changes.

Every event is written twice:
- a row in `security_events`, so people can review their own recent activity in Settings and
  spot sign-ins they didn't make (GET /api/v1/auth/activity);
- a JSON line on the "fintrack.audit" logger, for whoever runs the server.

Only IDs, IP addresses and browsers are recorded, never names, amounts or anything else from
the household's finances. `record` doesn't commit: the caller's transaction does.
"""

import json
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import SecurityEvent
from app.repositories import security_event_repo

log = logging.getLogger("fintrack.audit")

RETENTION = timedelta(days=365)


def record(
    db: Session,
    event: str,
    *,
    user_id: int | None = None,
    household_id: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    **details: Any,
) -> None:
    """Add one event to the session (committed with the caller's work) and log it."""
    security_event_repo.add(
        db,
        SecurityEvent(
            event=event,
            user_id=user_id,
            household_id=household_id,
            ip=(ip or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
            details=details,
        ),
    )
    log.info(
        json.dumps(
            {"event": event, "user_id": user_id, "household_id": household_id, "ip": ip, **details},
            default=str,
        )
    )


def record_for(db: Session, ctx: Any, event: str, **details: Any) -> None:
    """Record an event done by the signed-in user (`ctx` is an auth_service.AuthContext)."""
    record(
        db,
        event,
        user_id=ctx.user.id,
        household_id=ctx.household_id,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
        **details,
    )


def prune(db: Session) -> None:
    """Housekeeping, run on each login: forget events older than a year."""
    security_event_repo.delete_older_than(db, utcnow() - RETENTION)
