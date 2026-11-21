"""Manual accounts and transactions: balances, pagination, validation and permissions."""

from app.models import Account
from app.models.enums import Role, Source
from tests.conftest import join_household, make_client, signup


def create_cash(client, **overrides) -> dict:
    """Create a manual account with a $100 opening balance."""
    body = {"name": "Cash", "kind": "checking", "opening_balance_cents": 10000, **overrides}
    resp = client.post("/api/v1/accounts", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def add_txn(client, account_id, amount, description="Coffee", date="2026-10-01"):
    return client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "date": date,
            "amount_cents": amount,
            "description": description,
        },
    )


def test_manual_account_balance_tracks_transactions(client, owner):
    cash = create_cash(client)
    assert cash["balance_cents"] == 10000
    assert cash["owner_user_id"] == owner["user"]["id"]

    t1 = add_txn(client, cash["id"], -450).json()
    add_txn(client, cash["id"], 2000, "Sold a chair")
    accounts = client.get("/api/v1/accounts").json()
    assert accounts[0]["balance_cents"] == 10000 - 450 + 2000

    client.patch(f"/api/v1/transactions/{t1['id']}", json={"amount_cents": -1000})
    assert client.get("/api/v1/accounts").json()[0]["balance_cents"] == 10000 - 1000 + 2000

    client.delete(f"/api/v1/transactions/{t1['id']}")
    assert client.get("/api/v1/accounts").json()[0]["balance_cents"] == 12000

    client.patch(f"/api/v1/accounts/{cash['id']}", json={"opening_balance_cents": 0})
    assert client.get("/api/v1/accounts").json()[0]["balance_cents"] == 2000


def test_transactions_listed_newest_first_with_pagination(client, owner):
    cash = create_cash(client)
    for day in range(1, 8):
        add_txn(client, cash["id"], -100 * day, f"Item {day}", date=f"2026-10-0{day}")

    page1 = client.get("/api/v1/transactions", params={"limit": 3}).json()
    assert [t["description"] for t in page1["items"]] == ["Item 7", "Item 6", "Item 5"]
    assert page1["items"][0]["editable"] is True

    page2 = client.get(
        "/api/v1/transactions", params={"limit": 3, "cursor": page1["next_cursor"]}
    ).json()
    assert [t["description"] for t in page2["items"]] == ["Item 4", "Item 3", "Item 2"]

    page3 = client.get(
        "/api/v1/transactions", params={"limit": 3, "cursor": page2["next_cursor"]}
    ).json()
    assert [t["description"] for t in page3["items"]] == ["Item 1"]
    assert page3["next_cursor"] is None

    found = client.get("/api/v1/transactions", params={"q": "item 3"}).json()["items"]
    assert [t["description"] for t in found] == ["Item 3"]

    ranged = client.get(
        "/api/v1/transactions", params={"start": "2026-10-02", "end": "2026-10-03"}
    ).json()
    assert {t["description"] for t in ranged["items"]} == {"Item 2", "Item 3"}


def test_zero_amount_rejected(client, owner):
    cash = create_cash(client)
    assert add_txn(client, cash["id"], 0).status_code == 400


def test_manual_txn_rejected_on_synced_account(client, owner, db):
    synced = Account(
        household_id=owner["household"]["id"],
        source=Source.SIMPLEFIN,
        name="Checking",
        owner_user_id=owner["user"]["id"],
    )
    db.add(synced)
    db.commit()
    resp = add_txn(client, synced.id, -500)
    assert resp.status_code == 400
    assert resp.json()["code"] == "not_manual_account"


def test_reader_cannot_write(engine, client, owner, db):
    cash = create_cash(client)
    with make_client() as reader_client:
        reader = signup(reader_client, email="kid@example.com", name="Kid")
        join_household(
            db,
            user_id=reader["user"]["id"],
            household_id=owner["household"]["id"],
            role=Role.READER,
        )
        assert reader_client.get("/api/v1/auth/me").json()["role"] == "reader"
        resp = add_txn(reader_client, cash["id"], -100)
        assert resp.status_code == 403
        # ...but can read the household's shared data.
        accounts = reader_client.get("/api/v1/accounts", params={"scope": "household"}).json()
        assert [a["id"] for a in accounts] == [cash["id"]]


def test_cannot_touch_another_households_data(engine, client, owner):
    cash = create_cash(client)
    with make_client() as stranger:
        signup(stranger, email="stranger@example.com", name="Stranger")
        assert add_txn(stranger, cash["id"], -100).status_code == 404
        assert (
            stranger.patch(f"/api/v1/accounts/{cash['id']}", json={"kind": "savings"}).status_code
            == 404
        )
        assert stranger.get("/api/v1/accounts", params={"scope": "household"}).json() == []
