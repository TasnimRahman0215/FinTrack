"""Privacy rules: private accounts must never leak outside their owner's `me` view."""

import pytest


def ids(client, scope):
    """Account IDs `client` sees in `scope`."""
    return {a["id"] for a in client.get("/api/v1/accounts", params={"scope": scope}).json()}


@pytest.fixture
def accounts(client, owner, partner):
    """Alex (owner) and Sam (partner) each have a shared and a private account, plus a joint one."""
    partner_client, partner_me = partner

    def make(c, name, **kw):
        resp = c.post("/api/v1/accounts", json={"name": name, **kw})
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    return {
        "alex_shared": make(client, "Alex shared"),
        "alex_private": make(client, "Alex private", visibility="private"),
        "sam_shared": make(partner_client, "Sam shared"),
        "sam_private": make(partner_client, "Sam private", visibility="private"),
        "joint": make(client, "Joint", owner_user_id=None),
    }


def test_scopes(client, owner, partner, accounts):
    partner_client, partner_me = partner
    a = accounts
    sam_id = partner_me["user"]["id"]
    alex_id = owner["user"]["id"]

    assert ids(client, "me") == {a["alex_shared"], a["alex_private"], a["joint"]}
    assert ids(client, f"member:{sam_id}") == {a["sam_shared"], a["joint"]}
    assert ids(client, "household") == {a["alex_shared"], a["sam_shared"], a["joint"]}

    assert ids(partner_client, "me") == {a["sam_shared"], a["sam_private"], a["joint"]}
    assert ids(partner_client, f"member:{alex_id}") == {a["alex_shared"], a["joint"]}
    assert ids(partner_client, f"member:{sam_id}") == ids(partner_client, "me")


def test_private_account_hidden_from_partner_everywhere(client, partner, accounts):
    partner_client, _ = partner
    private = accounts["alex_private"]
    resp = partner_client.post(
        "/api/v1/transactions",
        json={"account_id": private, "date": "2026-10-01", "amount_cents": -1, "description": "x"},
    )
    assert resp.status_code == 404
    assert (
        partner_client.patch(f"/api/v1/accounts/{private}", json={"kind": "savings"}).status_code
        == 404
    )

    client.post(
        "/api/v1/transactions",
        json={
            "account_id": private,
            "date": "2026-10-01",
            "amount_cents": -999,
            "description": "Secret",
        },
    )
    for scope in ("household", "me"):
        items = partner_client.get("/api/v1/transactions", params={"scope": scope}).json()["items"]
        assert all(t["description"] != "Secret" for t in items)
        summary = partner_client.get("/api/v1/summary", params={"scope": scope}).json()
        assert summary["net_worth_cents"] == 0  # no balances anywhere visible to Sam


def test_partner_cannot_change_visibility_of_my_account(partner, accounts):
    partner_client, _ = partner
    resp = partner_client.patch(
        f"/api/v1/accounts/{accounts['alex_shared']}", json={"visibility": "private"}
    )
    assert resp.status_code == 403


def test_hidden_accounts_excluded_unless_requested(client, accounts):
    client.patch(f"/api/v1/accounts/{accounts['alex_shared']}", json={"is_hidden": True})
    assert accounts["alex_shared"] not in ids(client, "me")
    with_hidden = client.get(
        "/api/v1/accounts", params={"scope": "me", "include_hidden": True}
    ).json()
    assert accounts["alex_shared"] in {a["id"] for a in with_hidden}


def test_invalid_scope_and_unknown_member(client, owner):
    assert client.get("/api/v1/accounts", params={"scope": "everyone"}).status_code == 400
    assert client.get("/api/v1/accounts", params={"scope": "member:9999"}).status_code == 404


def test_summary_by_owner(client, owner, partner, accounts):
    client.patch(
        f"/api/v1/accounts/{accounts['alex_shared']}", json={"opening_balance_cents": 5000}
    )
    partner_client, _ = partner
    partner_client.patch(
        f"/api/v1/accounts/{accounts['sam_shared']}", json={"opening_balance_cents": 3000}
    )
    client.patch(f"/api/v1/accounts/{accounts['joint']}", json={"opening_balance_cents": -1000})

    s = client.get("/api/v1/summary", params={"scope": "household"}).json()
    assert s["net_worth_cents"] == 7000
    assert s["assets_cents"] == 8000
    assert s["liabilities_cents"] == -1000
    assert {o["name"]: o["total_cents"] for o in s["by_owner"]} == {
        "Alex": 5000,
        "Sam": 3000,
        "Joint": -1000,
    }
