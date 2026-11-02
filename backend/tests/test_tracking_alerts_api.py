from datetime import date

import httpx
import pytest

from tests.conftest import create_account, register, upload_bank_fixture

pytestmark = pytest.mark.anyio


@pytest.fixture
async def loaded(client: httpx.AsyncClient, auth: dict[str, str]) -> dict[str, str]:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    return auth


async def _spend(
    client: httpx.AsyncClient, headers: dict[str, str], day: str, amount: str, merchant: str
) -> None:
    resp = await client.post(
        "/api/v1/transactions",
        json={"txn_date": day, "amount": amount, "direction": "debit", "merchant": merchant},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


async def _alerts(client: httpx.AsyncClient, headers: dict[str, str]) -> set[tuple[str, str]]:
    body = (await client.get("/api/v1/alerts", headers=headers)).json()
    return {(a["type"], a["message"]) for a in body["alerts"]}


async def test_safe_to_spend_pace_and_alerts_mid_month(
    client: httpx.AsyncClient, loaded: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = (
        await client.post("/api/v1/plans/generate", params={"month": "2026-11"}, headers=loaded)
    ).json()
    await client.post(f"/api/v1/plans/{plan['id']}/activate", headers=loaded)
    monkeypatch.setattr("app.core.clock.today", lambda: date(2026, 11, 15))

    await _spend(client, loaded, "2026-11-03", "400", "Swiggy")
    await _spend(client, loaded, "2026-11-10", "500", "Swiggy")

    t = (await client.get("/api/v1/plans/current/tracking", headers=loaded)).json()
    assert (t["days_elapsed"], t["days_left"]) == (15, 16)
    # Flexible lines: food 1070 + shopping 650 + groceries 390 + other 160 + transport 115 = 2385
    assert t["flexible_planned"] == "2385.00"
    assert t["flexible_spent"] == "900.00"
    assert t["safe_to_spend"] == "92.00"  # (2385 − 900) ÷ 16 days, rounded down
    food = next(r for r in t["rows"] if r["planned"] == "1070.00")
    assert food["projected"] == "1800.00"  # 900 ÷ 15 days × 30
    assert food["pace_warning"] is True

    alerts = await _alerts(client, loaded)
    assert ("budget_80", "Food & Dining is at 84% with 16 days left") in alerts
    assert ("pace", "At this pace, Food & Dining ends ₹730 over") in alerts
    assert ("income_missing", "Acme Tech (Salary) hasn't arrived yet this month") in alerts

    # A big order: over budget, and unusual against the last 90 days of food spend.
    await _spend(client, loaded, "2026-11-12", "2000", "Zomato")
    # Rent went up.
    await _spend(client, loaded, "2026-11-05", "10000", "Ramesh Kumar")
    alerts = await _alerts(client, loaded)
    assert ("budget_100", "Food & Dining is ₹1,830 over budget") in alerts
    assert ("anomaly", "₹2,000 at Zomato is unusual for Food & Dining") in alerts
    assert ("recurring_change", "Ramesh Kumar went from ₹9,000 to ₹10,000") in alerts

    # Alerts never repeat for the same type, category and month.
    body = (await client.get("/api/v1/alerts", headers=loaded)).json()
    keys = [(a["type"], a["category_id"]) for a in body["alerts"]]
    assert len(keys) == len(set(keys))
    unread = body["unread"]
    assert unread == len(keys)

    first = body["alerts"][0]
    marked = (await client.patch(f"/api/v1/alerts/{first['id']}/read", headers=loaded)).json()
    assert marked["read"] is True
    assert (await client.get("/api/v1/alerts", headers=loaded)).json()["unread"] == unread - 1
    assert (await client.post("/api/v1/alerts/read-all", headers=loaded)).status_code == 204
    after = (await client.get("/api/v1/alerts", params={"unread": True}, headers=loaded)).json()
    assert after["unread"] == 0 and after["alerts"] == []


async def test_month_end_review(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    plan = (
        await client.post("/api/v1/plans/generate", params={"month": "2026-10"}, headers=loaded)
    ).json()
    await client.post(f"/api/v1/plans/{plan['id']}/activate", headers=loaded)

    review = (await client.get(f"/api/v1/plans/{plan['id']}/review", headers=loaded)).json()
    assert review["status"] == "closed"  # it's 1 Nov: October is over
    assert review["next_month"] == "2026-11"
    assert review["income"] == {"planned": "30000.00", "actual": "30112.00"}
    assert review["spending"]["actual"] == "15848.00"
    assert review["savings"] == {"planned": "6000.00", "actual": "14264.00"}
    assert review["savings_hit"] is True
    assert review["savings_diff"] == "8264.00"
    assert len(review["overspends"]) == 3
    assert all(float(c["diff"]) < 0 for c in review["overspends"])
    labels = {c["label"] for c in review["categories"]}
    assert "on_target" in labels  # rent and EMI landed exactly on plan
    assert 1 <= len(review["insights"]) <= 3

    # Closed months can't be edited.
    item = plan["items"][0]
    resp = await client.patch(
        f"/api/v1/plans/{plan['id']}/items/{item['id']}",
        json={"planned_amount": "1"},
        headers=loaded,
    )
    assert resp.json()["error"]["code"] == "PLAN_CLOSED"


async def test_insights_endpoint(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    body = (
        await client.get("/api/v1/analytics/insights", params={"month": "2026-10"}, headers=loaded)
    ).json()
    kinds = [i["kind"] for i in body["insights"]]
    assert kinds[0] == "savings"
    assert "biggest" in kinds
    assert 3 <= len(kinds) <= 5
    biggest = next(i for i in body["insights"] if i["kind"] == "biggest")
    assert biggest["body"] == "Rent took ₹9,000 — 57% of your spending."


async def test_review_queue_and_income_answer(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    queue = (await client.get("/api/v1/transactions/review", headers=loaded)).json()
    assert [t["merchant"] for t in queue["uncategorized"]] == ["Raju Auto Works"]
    assert [t["merchant"] for t in queue["unknown_credits"]] == ["Kiran Rao"]
    assert queue["total"] == 2

    cats = {
        c["name"]: c["id"] for c in (await client.get("/api/v1/categories", headers=loaded)).json()
    }
    kiran = queue["unknown_credits"][0]
    resp = await client.patch(
        f"/api/v1/transactions/{kiran['id']}",
        json={"category_id": cats["Freelance"], "apply_to_merchant": True},
        headers=loaded,
    )
    assert resp.json()["transaction"]["kind"] == "income"
    # The answer became a rule for that sender.
    rules = (await client.get("/api/v1/merchant-rules", headers=loaded)).json()
    assert ("Kiran Rao", cats["Freelance"]) in [(r["pattern"], r["category_id"]) for r in rules]
    queue = (await client.get("/api/v1/transactions/review", headers=loaded)).json()
    assert queue["unknown_credits"] == []


async def test_other_users_alerts_and_reviews_are_404(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    plan = (
        await client.post("/api/v1/plans/generate", params={"month": "2026-10"}, headers=loaded)
    ).json()
    await client.post(f"/api/v1/plans/{plan['id']}/activate", headers=loaded)
    alerts = (await client.get("/api/v1/alerts", headers=loaded)).json()["alerts"]
    other = await register(client, "b@example.com", "Bala Iyer")
    assert (
        await client.get(f"/api/v1/plans/{plan['id']}/review", headers=other)
    ).status_code == 404
    if alerts:
        resp = await client.patch(f"/api/v1/alerts/{alerts[0]['id']}/read", headers=other)
        assert resp.status_code == 404
    assert (await client.get("/api/v1/alerts", headers=other)).json()["alerts"] == []
    assert (await client.get("/api/v1/transactions/review", headers=other)).json()["total"] == 0


async def test_payee_history_not_sure_and_small_spends(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    """Paying people on UPI: history to jog memory, "not sure", and filing small ones at once."""
    phonepe = await create_account(client, auth, name="PhonePe", type="upi", last4=None)
    body = (
        b"Date,Time,Transaction Details,Transaction ID,UTR,Transaction Type,"
        b"Credit/debit instrument,Amount\n"
        b'"Oct 20, 2026","08:40 am","Paid to Venkatesh R","T1","402918391001","DEBIT","x","40"\n'
        b'"Oct 22, 2026","09:05 am","Paid to Venkatesh R","T2","402918391002","DEBIT","x","30"\n'
        b'"Oct 24, 2026","08:55 am","Paid to Venkatesh R","T3","402918391003","DEBIT","x","50"\n'
        b'"Oct 25, 2026","07:30 pm","Paid to Chaitra S","T4","402918391004","DEBIT","x","650"\n'
    )
    resp = await client.post(
        "/api/v1/uploads",
        headers=auth,
        data={"account_id": phonepe["id"], "source_type": "phonepe"},
        files={"file": ("phonepe.csv", body, "text/csv")},
    )
    assert resp.status_code == 202, resp.text

    queue = (await client.get("/api/v1/transactions/review", headers=auth)).json()
    assert len(queue["uncategorized"]) == 4
    assert queue["uncategorized"][0]["txn_time"] is not None
    venkatesh = queue["payee_stats"]["Venkatesh R"]
    assert venkatesh["count"] == 3
    assert (venkatesh["min_amount"], venkatesh["max_amount"]) == ("30.00", "50.00")
    assert venkatesh["median_amount"] == "40.00"
    assert venkatesh["usual_time"] == "morning"
    assert queue["payee_stats"]["Chaitra S"]["usual_time"] == "evening"

    cats = {
        c["name"]: c["id"] for c in (await client.get("/api/v1/categories", headers=auth)).json()
    }
    small = [t["id"] for t in queue["uncategorized"] if float(t["amount"]) < 100]
    resp = await client.post(
        "/api/v1/transactions/bulk-categorize",
        json={"transaction_ids": small, "category_id": cats["Small Spends"]},
        headers=auth,
    )
    assert resp.json() == {"updated": 3}

    # "Not sure": keep it in Other, but take it (and the payee) off the review list.
    chaitra = next(t for t in queue["uncategorized"] if t["merchant"] == "Chaitra S")
    await client.patch(
        f"/api/v1/transactions/{chaitra['id']}",
        json={"category_id": cats["Other"], "apply_to_merchant": True},
        headers=auth,
    )
    queue = (await client.get("/api/v1/transactions/review", headers=auth)).json()
    assert queue["uncategorized"] == []

    # Someone else's transactions can't be bulk-filed.
    other = await register(client, "b@example.com", "Bala Iyer")
    resp = await client.post(
        "/api/v1/transactions/bulk-categorize",
        json={"transaction_ids": small, "category_id": cats["Groceries"]},
        headers=other,
    )
    assert resp.json() == {"updated": 0}
