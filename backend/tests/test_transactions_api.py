import httpx
import pytest

from tests.conftest import create_account, upload_bank_fixture

pytestmark = pytest.mark.anyio


async def _category_id(client: httpx.AsyncClient, headers: dict[str, str], name: str) -> str:
    cats = (await client.get("/api/v1/categories", headers=headers)).json()
    return str(next(c["id"] for c in cats if c["name"] == name))


async def test_manual_cash_spend_is_categorized_by_rules(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "txn_date": "2026-10-20",
            "amount": "180.50",
            "direction": "debit",
            "merchant": "Chaayos cafe",
            "note": "with team",
        },
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    txn = resp.json()
    assert txn["amount"] == "180.50"
    assert txn["upload_id"] is None
    assert txn["kind"] == "expense"
    assert txn["category_id"] == await _category_id(client, auth, "Food & Dining")
    accounts = (await client.get("/api/v1/accounts", headers=auth)).json()
    assert next(a for a in accounts if a["id"] == txn["account_id"])["type"] == "cash"


async def test_manual_cash_income_defaults_to_income(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "txn_date": "2026-10-01",
            "amount": "2000",
            "direction": "credit",
            "merchant": "Tuition from neighbour",
        },
        headers=auth,
    )
    assert resp.json()["kind"] == "income"


async def test_manual_entry_validation(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    resp = await client.post(
        "/api/v1/transactions",
        json={"txn_date": "2026-10-01", "amount": "-5", "direction": "debit", "merchant": "x"},
        headers=auth,
    )
    assert resp.status_code == 422


async def test_recategorize_with_apply_to_merchant(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    groceries = await _category_id(client, auth, "Groceries")

    swiggy = (
        await client.get("/api/v1/transactions", params={"merchant": "Swiggy"}, headers=auth)
    ).json()
    assert swiggy["total"] == 3
    first = swiggy["items"][0]

    resp = await client.patch(
        f"/api/v1/transactions/{first['id']}",
        json={"category_id": groceries, "apply_to_merchant": True},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recategorized"] == 2
    assert body["transaction"]["categorized_by"] == "user"

    after = (
        await client.get("/api/v1/transactions", params={"merchant": "Swiggy"}, headers=auth)
    ).json()["items"]
    assert {t["category_id"] for t in after} == {groceries}
    assert sorted(t["categorized_by"] for t in after) == ["override", "override", "user"]

    rules = (await client.get("/api/v1/merchant-rules", headers=auth)).json()
    assert [(r["pattern"], r["match_type"]) for r in rules] == [("Swiggy", "exact")]

    # A later upload from the same merchant follows the user's rule
    resp = await client.post(
        "/api/v1/transactions",
        json={"txn_date": "2026-10-30", "amount": "99", "direction": "debit", "merchant": "Swiggy"},
        headers=auth,
    )
    assert resp.json()["category_id"] == groceries
    assert resp.json()["categorized_by"] == "override"


async def test_hand_set_rows_survive_merchant_rule(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    food = await _category_id(client, auth, "Food & Dining")
    shopping = await _category_id(client, auth, "Shopping")
    items = (
        await client.get("/api/v1/transactions", params={"merchant": "Zomato"}, headers=auth)
    ).json()["items"]
    pinned, other = items[0], items[1]

    await client.patch(
        f"/api/v1/transactions/{pinned['id']}", json={"category_id": shopping}, headers=auth
    )
    await client.patch(
        f"/api/v1/transactions/{other['id']}",
        json={"category_id": food, "apply_to_merchant": True},
        headers=auth,
    )
    refreshed = (
        await client.get("/api/v1/transactions", params={"merchant": "Zomato"}, headers=auth)
    ).json()["items"]
    assert {t["id"]: t["category_id"] for t in refreshed}[pinned["id"]] == shopping


async def test_moving_to_self_transfer_changes_kind(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    raju = (
        await client.get("/api/v1/transactions", params={"search": "raju"}, headers=auth)
    ).json()["items"][0]
    resp = await client.patch(
        f"/api/v1/transactions/{raju['id']}",
        json={"category_id": await _category_id(client, auth, "Self Transfer"), "note": "mine"},
        headers=auth,
    )
    assert resp.json()["transaction"]["kind"] == "self_transfer"
    assert resp.json()["transaction"]["note"] == "mine"


async def test_only_manual_entries_can_be_deleted(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    imported = (await client.get("/api/v1/transactions", headers=auth)).json()["items"][0]
    resp = await client.delete(f"/api/v1/transactions/{imported['id']}", headers=auth)
    assert resp.status_code == 409

    manual = (
        await client.post(
            "/api/v1/transactions",
            json={
                "txn_date": "2026-10-20",
                "amount": "50",
                "direction": "debit",
                "merchant": "Chai",
            },
            headers=auth,
        )
    ).json()
    resp = await client.delete(f"/api/v1/transactions/{manual['id']}", headers=auth)
    assert resp.status_code == 204


async def test_filters(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])

    async def total(**params: object) -> int:
        resp = await client.get("/api/v1/transactions", params=params, headers=auth)
        return int(resp.json()["total"])

    assert await total() == 24
    assert await total(start="2026-10-01", end="2026-10-31") == 14
    assert await total(kind="income") == 4
    assert await total(direction="credit") == 7
    assert await total(min_amount="9000") == 6
    assert await total(search="zomato") == 2
    assert await total(size=5) == 24
    resp = await client.get("/api/v1/transactions", params={"size": 500}, headers=auth)
    assert resp.status_code == 422
