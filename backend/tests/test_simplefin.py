"""SimpleFIN client and mapper: token decoding, HTTP flow (mocked), windows and errors.

No real network calls: httpx.MockTransport stands in for SimpleFIN Bridge.
"""

import base64
from datetime import datetime, timedelta

import httpx
import pytest

from app.core.errors import AppError, ProviderAuthError
from app.providers.simplefin import client as sf_client
from app.providers.simplefin.mapper import map_response, to_cents
from app.providers.simplefin.provider import SimpleFINProvider, date_windows
from tests.conftest import load_fixture

ACCESS_URL = "https://user:secret@bridge.example.com/simplefin"


@pytest.mark.parametrize(
    ("value", "cents"),
    [("12.34", 1234), ("-0.01", -1), ("100", 10000), ("1.005", 101), ("", None), (None, None)],
)
def test_to_cents(value, cents):
    assert to_cents(value) == cents


def test_map_response():
    result = map_response(load_fixture("simplefin_accounts.json"))
    assert result.errors == ["Connection to Robinhood may need attention"]
    assert [a.name for a in result.accounts] == ["Total Checking", "Gold Card", "Individual"]

    checking = result.accounts[0]
    assert checking.org_name == "Chase"
    assert checking.balance_cents == 253417
    assert checking.available_cents == 250000

    groceries, payroll, pending = checking.transactions
    assert groceries.amount_cents == -4567
    assert groceries.payee == "Whole Foods"
    assert groceries.memo is None
    assert groceries.date == groceries.transacted_at.date()  # purchase date preferred
    assert payroll.amount_cents == 320000 and not payroll.pending
    assert pending.pending and pending.posted_at is None

    holding = result.accounts[2].holdings[0]
    assert holding.symbol == "VTI" and holding.market_value_cents == 1102133


def test_decode_setup_token():
    token = base64.b64encode(b"https://bridge.example.com/simplefin/claim/abc").decode()
    assert sf_client.decode_setup_token(token) == "https://bridge.example.com/simplefin/claim/abc"
    with pytest.raises(AppError):
        sf_client.decode_setup_token("not-a-token!!")


def test_claim_and_fetch_with_mock_transport():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, text=ACCESS_URL)
        seen["auth"] = request.headers.get("authorization")
        seen["params"] = dict(request.url.params)
        assert request.url.path == "/simplefin/accounts"
        return httpx.Response(200, json=load_fixture("simplefin_accounts.json"))

    provider = SimpleFINProvider(httpx.Client(transport=httpx.MockTransport(handler)))
    token = base64.b64encode(b"https://bridge.example.com/simplefin/claim/abc").decode()
    credentials, label = provider.connect(token)
    assert credentials == ACCESS_URL
    assert "bridge.example.com" in label

    result = provider.fetch(credentials, None, None)
    assert len(result.accounts) == 3
    assert seen["auth"] == "Basic " + base64.b64encode(b"user:secret").decode()
    assert seen["params"]["pending"] == "1"


def test_long_range_fetched_in_45_day_windows():
    starts = []

    def handler(request: httpx.Request) -> httpx.Response:
        starts.append(int(request.url.params["start-date"]))
        data = load_fixture("simplefin_accounts.json")
        # Each window reports a different balance; the newest (last) window must win.
        data["accounts"][0]["balance"] = str(len(starts) * 100)
        return httpx.Response(200, json=data)

    provider = SimpleFINProvider(httpx.Client(transport=httpx.MockTransport(handler)))
    end = datetime(2026, 10, 1)
    result = provider.fetch(ACCESS_URL, end - timedelta(days=90), end)

    assert len(starts) == 2 and starts == sorted(starts)
    checking = result.accounts[0]
    assert checking.balance_cents == 20000
    assert len(checking.transactions) == 3  # same IDs in both windows are merged, not doubled
    assert result.errors == ["Connection to Robinhood may need attention"]


def test_date_windows():
    start = datetime(2026, 1, 1)
    windows = date_windows(start, start + timedelta(days=100))
    assert [(b - a).days for a, b in windows] == [45, 45, 10]
    assert date_windows(start, start + timedelta(days=14)) == [(start, start + timedelta(days=14))]


def test_fetch_403_is_auth_error():
    transport = httpx.MockTransport(lambda r: httpx.Response(403))
    with pytest.raises(ProviderAuthError):
        sf_client.fetch_accounts(ACCESS_URL, client=httpx.Client(transport=transport))


def test_claim_403_explains_reused_token():
    transport = httpx.MockTransport(lambda r: httpx.Response(403))
    token = base64.b64encode(b"https://bridge.example.com/claim/x").decode()
    with pytest.raises(AppError, match="already have been used"):
        sf_client.claim_access_url(token, client=httpx.Client(transport=transport))
