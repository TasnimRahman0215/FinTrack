"""Logging setup, called once from app/main.py. Modules log via `logging.getLogger("fintrack")`."""

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
