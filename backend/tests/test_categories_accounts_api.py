import httpx
import pytest

from tests.conftest import create_account

pytestmark = pytest.mark.anyio


async def test_system_categories_are_seeded_and_read_only(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    cats = (await client.get("/api/v1/categories", headers=auth)).json()
    names = {c["name"] for c in cats}
    assert {"Food & Dining", "Salary", "Self Transfer", "Other"} <= names
    assert all(c["is_system"] for c in cats)
    food = next(c for c in cats if c["name"] == "Food & Dining")
    resp = await client.patch(
        f"/api/v1/categories/{food['id']}", json={"name": "Hacked"}, headers=auth
    )
    assert resp.status_code == 404


async def test_user_category_lifecycle_moves_rows_to_other(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    pets = (
        await client.post(
            "/api/v1/categories",
            json={"name": "Pets", "bucket": "variable", "icon": "paw-print", "color": "#2a78d6"},
            headers=auth,
        )
    ).json()
    assert pets["is_system"] is False

    resp = await client.patch(
        f"/api/v1/categories/{pets['id']}", json={"name": "Pet care"}, headers=auth
    )
    assert resp.json()["name"] == "Pet care"

    txn = (
        await client.post(
            "/api/v1/transactions",
            json={
                "txn_date": "2026-10-05",
                "amount": "640",
                "direction": "debit",
                "merchant": "Heads Up For Tails",
                "category_id": pets["id"],
            },
            headers=auth,
        )
    ).json()
    assert txn["categorized_by"] == "user"

    rule = await client.post(
        "/api/v1/merchant-rules",
        json={"pattern": "heads up", "category_id": pets["id"]},
        headers=auth,
    )
    assert rule.status_code == 201

    assert (
        await client.delete(f"/api/v1/categories/{pets['id']}", headers=auth)
    ).status_code == 204
    cats = (await client.get("/api/v1/categories", headers=auth)).json()
    other = next(c["id"] for c in cats if c["name"] == "Other")
    moved = (await client.get("/api/v1/transactions", headers=auth)).json()["items"][0]
    assert moved["category_id"] == other
    assert (await client.get("/api/v1/merchant-rules", headers=auth)).json() == []


async def test_merchant_rules_crud_and_regex_validation(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    cats = (await client.get("/api/v1/categories", headers=auth)).json()
    groceries = next(c["id"] for c in cats if c["name"] == "Groceries")

    bad = await client.post(
        "/api/v1/merchant-rules",
        json={"pattern": "([", "match_type": "regex", "category_id": groceries},
        headers=auth,
    )
    assert bad.json()["error"]["code"] == "INVALID_REGEX"

    rule = (
        await client.post(
            "/api/v1/merchant-rules",
            json={"pattern": r"raju\s+stores?", "match_type": "regex", "category_id": groceries},
            headers=auth,
        )
    ).json()
    txn = (
        await client.post(
            "/api/v1/transactions",
            json={
                "txn_date": "2026-10-05",
                "amount": "320",
                "direction": "debit",
                "merchant": "Raju Store",
            },
            headers=auth,
        )
    ).json()
    assert txn["category_id"] == groceries
    assert txn["categorized_by"] == "override"

    resp = await client.delete(f"/api/v1/merchant-rules/{rule['id']}", headers=auth)
    assert resp.status_code == 204
    resp = await client.delete(f"/api/v1/merchant-rules/{rule['id']}", headers=auth)
    assert resp.status_code == 404


async def test_account_lifecycle_and_last4_masking(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth, last4="5010 0123 4567 8901")
    assert account["last4"] == "8901"
    assert account["has_column_mapping"] is False

    resp = await client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"name": "Salary account", "last4": "XXXX9999"},
        headers=auth,
    )
    assert (resp.json()["name"], resp.json()["last4"]) == ("Salary account", "9999")

    accounts = (await client.get("/api/v1/accounts", headers=auth)).json()
    assert {a["type"] for a in accounts} == {"bank", "cash"}  # cash account made at sign-up

    assert (
        await client.delete(f"/api/v1/accounts/{account['id']}", headers=auth)
    ).status_code == 204
    resp = await client.get("/api/v1/accounts", headers=auth)
    assert [a["type"] for a in resp.json()] == ["cash"]
