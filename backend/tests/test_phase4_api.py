import csv
import io
from typing import Any

import httpx
import pytest

from app.ml.train import seed_samples, train
from tests.conftest import FIXTURES, create_account, register

pytestmark = pytest.mark.anyio
NOVEMBER = {"period": "custom", "start": "2026-11-01", "end": "2026-11-30"}


async def _upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    account_id: str,
    source: str,
    name: str,
    password: str | None = None,
) -> dict[str, Any]:
    path = FIXTURES / name
    data = {"account_id": account_id, "source_type": source}
    if password:
        data["pdf_password"] = password
    mime = "application/pdf" if name.endswith(".pdf") else "application/octet-stream"
    resp = await client.post(
        "/api/v1/uploads",
        headers=headers,
        data=data,
        files={"file": (path.name, path.read_bytes(), mime)},
    )
    assert resp.status_code == 202, resp.text
    status = await client.get(f"/api/v1/uploads/{resp.json()['id']}", headers=headers)
    return dict(status.json())


async def _txns(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    resp = await client.get("/api/v1/transactions", params={"size": 200}, headers=headers)
    return list(resp.json()["items"])


async def test_sources_listed(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    sources = (await client.get("/api/v1/uploads/sources", headers=auth)).json()
    by_type = {s["source_type"]: s for s in sources}
    assert set(by_type) == {
        "generic_csv",
        "hdfc_pdf",
        "sbi_pdf",
        "icici_pdf",
        "hdfc_card_pdf",
        "gpay_pdf",
        "phonepe",
        "paytm",
    }
    assert by_type["hdfc_pdf"]["accepts_password"] is True
    assert by_type["gpay_pdf"]["group"] == "upi"


@pytest.mark.parametrize("bank_first", [True, False])
async def test_two_sources_without_double_counting(
    client: httpx.AsyncClient, auth: dict[str, str], bank_first: bool
) -> None:
    bank = await create_account(client, auth, name="HDFC Savings", institution="HDFC", last4="4321")
    gpay = await create_account(client, auth, name="Google Pay", type="upi", last4=None)
    phonepe = await create_account(client, auth, name="PhonePe", type="upi", last4=None)

    steps = [
        (bank["id"], "hdfc_pdf", "hdfc_statement.pdf"),
        (gpay["id"], "gpay_pdf", "gpay_statement.pdf"),
    ]
    for account_id, source, name in steps if bank_first else steps[::-1]:
        assert (await _upload(client, auth, account_id, source, name))["status"] == "done"
    phonepe_upload = await _upload(client, auth, phonepe["id"], "phonepe", "phonepe_statement.pdf")
    assert phonepe_upload["status"] == "done"

    summary = (await client.get("/api/v1/analytics/summary", params=NOVEMBER, headers=auth)).json()
    # Bank debits 450 + 9000 + 640 + 1299, plus the one payment only Google Pay saw (Chai 60).
    assert summary["spending"] == "11449.00"
    assert summary["income"] == "30000.00"

    txns = await _txns(client, auth)
    dups = [t for t in txns if t["dedup_of"]]
    # Swiggy, rent, Kiran: matched on UPI reference. Blinkit: PhonePe printed no UTR, so it
    # matched on amount, date and merchant name.
    assert sorted(t["merchant"] for t in dups) == ["Blinkit", "Kiran Rao", "Ramesh Kumar", "Swiggy"]
    kept_ids = {t["dedup_of"] for t in dups}
    assert {t["account_id"] for t in txns if t["id"] in kept_ids} == {bank["id"]}

    merchants = (
        await client.get("/api/v1/analytics/merchants", params=NOVEMBER, headers=auth)
    ).json()
    swiggy = next(m for m in merchants["merchants"] if m["merchant"] == "Swiggy")
    assert swiggy["count"] == 1


async def test_locked_pdf_then_retry_with_password(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    bank = await create_account(client, auth, name="HDFC Savings", last4="4321")
    failed = await _upload(client, auth, bank["id"], "hdfc_pdf", "hdfc_statement_locked.pdf")
    assert failed["status"] == "failed"
    assert failed["error"].startswith("PDF_PASSWORD_REQUIRED")

    # Same file again, now with the password: the failed attempt is replaced, not a duplicate.
    done = await _upload(
        client, auth, bank["id"], "hdfc_pdf", "hdfc_statement_locked.pdf", password="ASHA1234"
    )
    assert done["status"] == "done"
    assert done["txn_count"] == 6
    assert (await client.get("/api/v1/uploads", headers=auth)).json()["total"] == 1


async def test_ml_layer_in_pipeline(
    client: httpx.AsyncClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = train(seed_samples())
    monkeypatch.setattr("app.services.enrichment.get_model", lambda: model)
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "txn_date": "2026-11-03",
            "amount": "349",
            "direction": "debit",
            "merchant": "Dominoz Pizza",
        },
        headers=auth,
    )
    txn = resp.json()
    cats = {
        c["id"]: c["name"] for c in (await client.get("/api/v1/categories", headers=auth)).json()
    }
    assert cats[txn["category_id"]] == "Food & Dining"
    assert txn["categorized_by"] == "ml"
    assert txn["ml_model_version"] == model.version


async def test_export_csv(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    bank = await create_account(client, auth, name="HDFC Savings", last4="4321")
    gpay = await create_account(client, auth, name="Google Pay", type="upi", last4=None)
    await _upload(client, auth, bank["id"], "hdfc_pdf", "hdfc_statement.pdf")
    await _upload(client, auth, gpay["id"], "gpay_pdf", "gpay_statement.pdf")
    await client.post(
        "/api/v1/transactions",
        json={
            "txn_date": "2026-11-20",
            "amount": "40",
            "direction": "debit",
            "merchant": "=HYPERLINK(1)",
        },
        headers=auth,
    )
    resp = await client.get("/api/v1/export/transactions.csv", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 11  # 6 bank + 4 Google Pay + 1 manual
    assert sum(r["counted"] == "duplicate" for r in rows) == 3
    manual = next(r for r in rows if r["source"] == "manual entry")
    assert manual["merchant"].startswith("'=")  # spreadsheet formula neutralised


async def test_delete_account_removes_everything(client: httpx.AsyncClient) -> None:
    headers = await register(client, "gone@example.com", "Asha Verma")
    bank = await create_account(client, headers, name="HDFC Savings", last4="4321")
    await _upload(client, headers, bank["id"], "hdfc_pdf", "hdfc_statement.pdf")

    wrong = await client.request(
        "DELETE", "/api/v1/me", json={"password": "nope-nope"}, headers=headers
    )
    assert wrong.status_code == 401
    ok = await client.request(
        "DELETE", "/api/v1/me", json={"password": "correct-horse-1"}, headers=headers
    )
    assert ok.status_code == 204

    assert (await client.get("/api/v1/me", headers=headers)).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": "gone@example.com", "password": "correct-horse-1"}
    )
    assert login.status_code == 401
    # The email is free again, and the new account starts empty.
    fresh = await register(client, "gone@example.com", "Asha Verma")
    assert (await client.get("/api/v1/transactions", headers=fresh)).json()["total"] == 0
    assert (await client.get("/api/v1/uploads", headers=fresh)).json()["total"] == 0
