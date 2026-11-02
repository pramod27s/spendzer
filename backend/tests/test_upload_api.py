import re
from collections import Counter

import httpx
import pytest

from tests.conftest import FIXTURES, SPLIT_MAPPING, create_account, upload_bank_fixture, upload_file

pytestmark = pytest.mark.anyio


async def _categories(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    resp = await client.get("/api/v1/categories", headers=headers)
    return {c["id"]: c["name"] for c in resp.json()}


async def _all_txns(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict]:
    resp = await client.get("/api/v1/transactions", params={"size": 200}, headers=headers)
    assert resp.status_code == 200
    return list(resp.json()["items"])


async def test_sources_listed(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    resp = await client.get("/api/v1/uploads/sources", headers=auth)
    assert resp.status_code == 200
    assert resp.json()[0]["source_type"] == "generic_csv"
    assert resp.json()[0]["needs_column_mapping"] is True


async def test_first_upload_needs_mapping_then_parses(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    resp = await upload_file(client, auth, account["id"], FIXTURES / "bank_split_columns.csv")
    assert resp.status_code == 202
    upload_id = resp.json()["id"]

    status = (await client.get(f"/api/v1/uploads/{upload_id}", headers=auth)).json()
    assert status["status"] == "needs_mapping"
    assert status["preview"]["suggested_mapping"]["amount_mode"] == "split"

    resp = await client.post(
        f"/api/v1/uploads/{upload_id}/column-mapping", json=SPLIT_MAPPING, headers=auth
    )
    assert resp.status_code == 202
    status = (await client.get(f"/api/v1/uploads/{upload_id}", headers=auth)).json()
    assert status["status"] == "done"
    assert status["txn_count"] == 24
    assert (status["period_start"], status["period_end"]) == ("2026-08-01", "2026-10-31")
    assert status["preview"] is None

    accounts = (await client.get("/api/v1/accounts", headers=auth)).json()
    assert next(a for a in accounts if a["id"] == account["id"])["has_column_mapping"]


async def test_enrichment_results(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    names = await _categories(client, auth)
    txns = await _all_txns(client, auth)

    def find(fragment: str) -> dict:
        return next(t for t in txns if fragment in t["raw_description"])

    swiggy = find("SWIGGY/YESB/swiggy@ybl")
    assert (swiggy["merchant"], names[swiggy["category_id"]]) == ("Swiggy", "Food & Dining")
    assert swiggy["kind"] == "expense" and swiggy["categorized_by"] == "rule"

    assert names[find("Rent for Oct")["category_id"]] == "Rent"
    assert names[find("BAJAJ FINANCE")["category_id"]] == "EMI & Loans"
    assert names[find("BLINKIT")["category_id"]] == "Groceries"
    assert names[find("NETFLIX")["category_id"]] == "Subscriptions"
    assert names[find("RAJU AUTO WORKS")["category_id"]] == "Other"

    salary = find("ACMEN52026100112")
    assert (salary["kind"], names[salary["category_id"]]) == ("income", "Salary")
    assert salary["merchant"] == "Acme Tech (Salary)"

    assert find("ASHA VERMA")["kind"] == "self_transfer"
    assert find("REFUND")["kind"] == "refund"
    assert find("CASHBACK")["kind"] == "cashback"
    assert find("KIRAN RAO")["kind"] == "unknown"
    assert names[find("CREDIT INTEREST")["category_id"]] == "Interest"

    # No full card number survives into storage
    assert not any(re.search(r"\d{13,19}", t["raw_description"]) for t in txns)
    assert Counter(t["kind"] for t in txns)["expense"] == 16


async def test_saved_mapping_is_reused_and_duplicates_rejected(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])

    again = await upload_file(client, auth, account["id"], FIXTURES / "bank_split_columns.csv")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "DUPLICATE_FILE"

    # A different file with the same layout parses straight away with the saved mapping.
    tweaked = (FIXTURES / "bank_split_columns.csv").read_text().replace("620.00", "640.00")
    resp = await client.post(
        "/api/v1/uploads",
        headers=auth,
        data={"account_id": account["id"], "source_type": "generic_csv"},
        files={"file": ("nov.csv", tweaked.encode(), "text/csv")},
    )
    assert resp.status_code == 202
    status = (await client.get(f"/api/v1/uploads/{resp.json()['id']}", headers=auth)).json()
    assert status["status"] == "done"


async def test_upload_validation(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    account = await create_account(client, auth)
    base = {"account_id": account["id"], "source_type": "generic_csv"}

    resp = await client.post(
        "/api/v1/uploads",
        headers=auth,
        data=base,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE"

    resp = await client.post(
        "/api/v1/uploads",
        headers=auth,
        data={**base, "source_type": "nope"},
        files={"file": ("a.csv", b"Date,Amount\n01/01/2026,5", "text/csv")},
    )
    assert resp.json()["error"]["code"] == "UNKNOWN_SOURCE"

    big = b"a" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/uploads", headers=auth, data=base, files={"file": ("big.csv", big, "text/csv")}
    )
    assert resp.status_code == 413


async def test_bad_mapping_marks_upload_failed(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    resp = await upload_file(client, auth, account["id"], FIXTURES / "card_signed_amounts.csv")
    upload_id = resp.json()["id"]
    wrong = {
        "date_col": "Description",
        "description_col": "Description",
        "amount_mode": "signed",
        "amount_col": "Amount (INR)",
    }
    await client.post(f"/api/v1/uploads/{upload_id}/column-mapping", json=wrong, headers=auth)
    status = (await client.get(f"/api/v1/uploads/{upload_id}", headers=auth)).json()
    assert status["status"] == "failed"
    assert status["error"].startswith("NO_TRANSACTIONS")


async def test_delete_upload_removes_its_transactions(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    account = await create_account(client, auth)
    upload = await upload_bank_fixture(client, auth, account["id"])
    assert len(await _all_txns(client, auth)) == 24
    resp = await client.delete(f"/api/v1/uploads/{upload['id']}", headers=auth)
    assert resp.status_code == 204
    assert await _all_txns(client, auth) == []
