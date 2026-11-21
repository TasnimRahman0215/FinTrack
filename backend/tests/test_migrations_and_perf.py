"""Migrations produce the same tables as the models, and big datasets stay fast."""

import random
import time
from datetime import date, timedelta

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, inspect

from app.db.base import Base
from app.models import Account, Transaction
from app.models.enums import Source
from tests.conftest import load_fixture  # noqa: F401  (ensures env is configured)


def test_alembic_upgrade_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    migrated = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    assert migrated == set(Base.metadata.tables)


def test_list_and_summary_fast_with_50k_transactions(client, owner, db):
    """~3 years of heavy card use for a couple is ~30k rows; check 50k stays fast."""
    household_id = owner["household"]["id"]
    accounts = []
    for i in range(12):
        a = Account(
            household_id=household_id,
            source=Source.MANUAL,
            name=f"Account {i}",
            owner_user_id=owner["user"]["id"],
        )
        db.add(a)
        accounts.append(a)
    db.commit()

    rng = random.Random(1)
    start = date(2023, 10, 1)
    rows = [
        {
            "account_id": rng.choice(accounts).id,
            "source": Source.MANUAL,
            "date": start + timedelta(days=rng.randrange(1095)),
            "amount_cents": -rng.randrange(100, 20000),
            "description": f"Merchant {rng.randrange(500)}",
            "pending": False,
        }
        for _ in range(50_000)
    ]
    db.execute(insert(Transaction), rows)
    db.commit()

    def timed(path, **params):
        t0 = time.perf_counter()
        resp = client.get(path, params=params)
        assert resp.status_code == 200
        return time.perf_counter() - t0

    timings = {
        "first page": timed("/api/v1/transactions", scope="household"),
        "month filter": timed(
            "/api/v1/transactions", start="2025-03-01", end="2025-03-31", limit=200
        ),
        "search": timed("/api/v1/transactions", q="merchant 42"),
        "summary": timed("/api/v1/summary", scope="household"),
    }
    assert max(timings.values()) < 0.5, timings
