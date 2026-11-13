"""Shared pytest fixtures.

Each test gets a fresh SQLite file (`engine`), a TestClient that sends the CSRF header
(`client`), and optionally a signed-up household owner (`owner`) and a second member (`partner`).
No test touches your real database or the network.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path

from cryptography.fernet import Fernet

# Configure the app for tests before anything imports settings.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "RUN_SCHEDULER": "false",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "ALLOW_SIGNUP": "true",
        "DATABASE_URL": "sqlite:///:memory:",  # replaced per test by the `engine` fixture
        # The tests' mock SimpleFIN servers live on example.com.
        "SIMPLEFIN_ALLOWED_HOSTS": "simplefin.org,example.com",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import rate_limit  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, init_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HouseholdMembership, UserSession  # noqa: E402
from app.models.enums import Role  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
CLIENT_HEADERS = {"X-Requested-With": "fintrack"}
PASSWORD = "correct-horse-battery"


@pytest.fixture
def engine(tmp_path):
    eng = init_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_state():
    """Isolate tests: clear rate-limit counters and re-read settings for each test."""
    rate_limit.reset_all()
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_client() -> TestClient:
    """A new browser-like client with its own cookie jar."""
    return TestClient(app, headers=CLIENT_HEADERS)


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
    with make_client() as c:
        yield c


def signup(client: TestClient, email: str = "alex@example.com", name: str = "Alex") -> dict:
    """Sign up through the API (which also logs `client` in) and return the /me payload."""
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "display_name": name, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def owner(client) -> dict:
    """A signed-in owner of a fresh household. `client` carries their cookie."""
    return signup(client)


def join_household(db: Session, *, user_id: int, household_id: int, role: Role) -> None:
    """Stand-in for the future invite flow: add a membership and switch the user's sessions."""
    db.add(HouseholdMembership(household_id=household_id, user_id=user_id, role=role))
    for session in db.query(UserSession).filter_by(user_id=user_id):
        session.active_household_id = household_id
    db.commit()


@pytest.fixture
def partner(engine, owner, db) -> Iterator[tuple[TestClient, dict]]:
    """A second signed-in member of the owner's household (contributor)."""
    with make_client() as c:
        me = signup(c, email="sam@example.com", name="Sam")
        join_household(
            db,
            user_id=me["user"]["id"],
            household_id=owner["household"]["id"],
            role=Role.CONTRIBUTOR,
        )
        yield c, me


def load_fixture(name: str) -> dict:
    """Load a JSON file from tests/fixtures/ (sample provider responses, all made up)."""
    return json.loads((FIXTURES / name).read_text())
