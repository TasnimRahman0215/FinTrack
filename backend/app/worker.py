"""Standalone scheduler process: `python -m app.worker`.

Used by the optional `worker` service in docker-compose.yml, for people who prefer background
syncs outside the API process. When you run it, set RUN_SCHEDULER=false on the API.
"""

import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_engine
from app.jobs.scheduler import build_scheduler


def main() -> None:
    configure_logging(get_settings().log_level)
    get_engine()
    logging.getLogger("fintrack.worker").info("Worker started")
    build_scheduler(blocking=True).start()


if __name__ == "__main__":
    main()
