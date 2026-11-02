"""User B must never see or touch user A's data: every lookup is scoped by user_id."""

import httpx
import pytest

from tests.conftest import create_account, register, upload_bank_fixture

pytestmark = pytest.mark.anyio


async def test_user_b_gets_404_on_user_a_resources(client: httpx.AsyncClient) -> None:
    a = await register(client, "a@example.com", "Asha Verma")
    account = await create_account(client, a)
    upload = await upload_bank_fixture(client, a, account["id"])
    txn = (await client.get("/api/v1/transactions", headers=a)).json()["items"][0]
    cats = (await client.get("/api/v1/categories", headers=a)).json()
    own_cat = (
        await client.post(
            "/api/v1/categories", json={"name": "Pets", "bucket": "variable"}, headers=a
        )
    ).json()

    b = await register(client, "b@example.com", "Bala Iyer")

    assert (await client.get(f"/api/v1/uploads/{upload['id']}", headers=b)).status_code == 404
    assert (await client.delete(f"/api/v1/uploads/{upload['id']}", headers=b)).status_code == 404
    assert (
        await client.patch(f"/api/v1/transactions/{txn['id']}", json={"note": "x"}, headers=b)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/transactions/{txn['id']}", headers=b)).status_code == 404
    assert (
        await client.patch(f"/api/v1/accounts/{account['id']}", json={"name": "x"}, headers=b)
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/categories/{own_cat['id']}", headers=b)
    ).status_code == 404

    # B can't upload into A's account, or file A's category on B's rows
    resp = await client.post(
        "/api/v1/uploads",
        headers=b,
        data={"account_id": account["id"], "source_type": "generic_csv"},
        files={"file": ("x.csv", b"Date,Amount\n01/10/2026,5", "text/csv")},
    )
    assert resp.status_code == 404
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "txn_date": "2026-10-01",
            "amount": "5",
            "direction": "debit",
            "merchant": "x",
            "category_id": own_cat["id"],
        },
        headers=b,
    )
    assert resp.status_code == 404

    # Lists are scoped
    assert (await client.get("/api/v1/transactions", headers=b)).json()["total"] == 0
    assert (await client.get("/api/v1/uploads", headers=b)).json()["total"] == 0
    b_cats = (await client.get("/api/v1/categories", headers=b)).json()
    assert len(b_cats) == len(cats)  # system categories only; A's "Pets" is invisible
    summary = (
        await client.get("/api/v1/analytics/summary", params={"period": "last_12"}, headers=b)
    ).json()
    assert summary["has_data"] is False
