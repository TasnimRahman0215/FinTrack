"""Background jobs. Runs inside the API process by default (RUN_SCHEDULER=true), or in a
separate worker container via `python -m app.worker` (then set RUN_SCHEDULER=false on the API).
Run only ONE scheduler per database.

Built by app/main.py (in-process) and app/worker.py (standalone).
"""

from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from app.jobs.sync_job import run_due_syncs

CHECK_EVERY_MINUTES = 30  # each check only syncs connections that are actually due


def build_scheduler(*, blocking: bool = False) -> BaseScheduler:
    scheduler: BaseScheduler = (
        BlockingScheduler(timezone="UTC") if blocking else BackgroundScheduler(timezone="UTC")
    )
    scheduler.add_job(
        run_due_syncs,
        "interval",
        minutes=CHECK_EVERY_MINUTES,
        id="sync_due_connections",
        next_run_time=datetime.now(UTC) + timedelta(minutes=1),  # catch up shortly after boot
        max_instances=1,
        coalesce=True,
    )
    return scheduler
