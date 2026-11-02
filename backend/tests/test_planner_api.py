from typing import Any

import httpx
import pytest

from tests.conftest import create_account, register, upload_bank_fixture

pytestmark = pytest.mark.anyio


@pytest.fixture
async def loaded(client: httpx.AsyncClient, auth: dict[str, str]) -> dict[str, str]:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    return auth


async def _names(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    cats = (await client.get("/api/v1/categories", headers=headers)).json()
    return {c["id"]: c["name"] for c in cats}


async def _generate(
    client: httpx.AsyncClient, headers: dict[str, str], month: str = "2026-11", **body: Any
) -> httpx.Response:
    return await client.post(
        "/api/v1/plans/generate", params={"month": month}, json=body or None, headers=headers
    )


def _lines(plan: dict[str, Any], names: dict[str, str]) -> dict[tuple[str, str], str]:
    return {(names[i["category_id"]], i["source"]): i["planned_amount"] for i in plan["items"]}


async def test_recurring_detected_after_upload(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    body = (await client.get("/api/v1/recurring", headers=loaded)).json()
    groups = {g["merchant"]: g for g in body["groups"]}
    assert set(groups) == {"Ramesh Kumar", "Bajaj Finance"}  # Swiggy amounts vary too much
    assert groups["Ramesh Kumar"]["typical_amount"] == "9000.00"
    assert groups["Ramesh Kumar"]["typical_day"] == 5
    assert groups["Bajaj Finance"]["frequency"] == "monthly"
    assert body["monthly_total"] == "11500.00"

    rent = (
        await client.get(
            "/api/v1/transactions", params={"merchant": "Ramesh Kumar"}, headers=loaded
        )
    ).json()["items"]
    assert all(t["is_recurring"] for t in rent)


async def test_generate_plan_from_history(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    resp = await _generate(client, loaded)
    assert resp.status_code == 201, resp.text
    plan = resp.json()
    names = await _names(client, loaded)

    assert plan["status"] == "draft"
    assert plan["expected_income"] == "30000.00"
    assert plan["income_basis"] == "Median income of Aug–Oct"
    assert plan["savings_target"] == "6000.00"  # 20% default
    assert _lines(plan, names) == {
        ("Rent", "fixed"): "9000.00",
        ("EMI & Loans", "fixed"): "2500.00",
        ("Food & Dining", "forecast"): "1070.00",  # median of 1070, 380, 1070
        ("Shopping", "forecast"): "650.00",  # 0.5 × 1299, other months empty
        ("Groceries", "forecast"): "390.00",
        ("Subscriptions", "forecast"): "325.00",
        ("Other", "forecast"): "160.00",
        ("Transport", "forecast"): "115.00",
    }
    rent = next(i for i in plan["items"] if names[i["category_id"]] == "Rent")
    assert rent["basis"] == "Recurring: Ramesh Kumar ₹9,000"
    fit = plan["fit"]
    assert (fit["spendable"], fit["planned_total"], fit["gap"]) == (
        "24000.00",
        "14210.00",
        "-9790.00",
    )
    assert fit["status"] == "surplus"


async def test_no_income_history_requires_expected_income(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    resp = await _generate(client, auth)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INCOME_REQUIRED"

    resp = await _generate(client, auth, expected_income="25000")
    assert resp.status_code == 201
    plan = resp.json()
    assert (plan["expected_income"], plan["income_custom"]) == ("25000.00", True)
    assert plan["savings_target"] == "5000.00"
    assert plan["items"] == []


async def test_gap_fixed_by_suggested_cuts(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    # Savings 54.3% of 30,000 = 16,290 → spendable 13,710 vs 14,210 planned: 500 over.
    plan = (await _generate(client, loaded, savings_target_pct="54.3")).json()
    names = await _names(client, loaded)
    fit = plan["fit"]
    assert (fit["gap"], fit["status"]) == ("500.00", "over_fixable")
    [cut] = fit["cuts"]
    assert names[cut["category_id"]] == "Food & Dining"  # largest discretionary line first
    assert (cut["current"], cut["suggested"]) == ("1070.00", "570.00")

    applied = (
        await client.post(f"/api/v1/plans/{plan['id']}/apply-suggestions", headers=loaded)
    ).json()
    assert applied["fit"]["status"] == "balanced"
    food = next(i for i in applied["items"] if names[i["category_id"]] == "Food & Dining")
    assert (food["planned_amount"], food["source"]) == ("570.00", "user")
    # The savings target was never touched to make it fit.
    assert applied["savings_target"] == plan["savings_target"]


async def test_gap_cuts_cannot_fix(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    plan = (await _generate(client, loaded, savings_target_pct="60")).json()
    fit = plan["fit"]
    assert fit["gap"] == "2210.00"
    assert fit["status"] == "over_unfixable"
    # Discretionary to 50% (535 + 325 + 80), variable to 80% (78 + 23); fixed lines untouched.
    assert fit["gap_after_cuts"] == "1169.00"
    assert plan["savings_target"] == "18000.00"


async def test_regenerate_keeps_user_edits(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    plan = (await _generate(client, loaded)).json()
    names = await _names(client, loaded)
    food = next(i for i in plan["items"] if names[i["category_id"]] == "Food & Dining")

    edited = (
        await client.patch(
            f"/api/v1/plans/{plan['id']}/items/{food['id']}",
            json={"planned_amount": "2000"},
            headers=loaded,
        )
    ).json()
    line = next(i for i in edited["items"] if names[i["category_id"]] == "Food & Dining")
    assert (line["planned_amount"], line["source"]) == ("2000.00", "user")
    assert line["basis"] == "Set by you (was ₹1,070)"

    await client.patch(
        f"/api/v1/plans/{plan['id']}", json={"expected_income": "32000"}, headers=loaded
    )
    again = (await _generate(client, loaded)).json()
    assert again["id"] == plan["id"]
    lines = _lines(again, names)
    assert lines[("Food & Dining", "user")] == "2000.00"
    assert ("Food & Dining", "forecast") not in lines
    assert again["expected_income"] == "32000.00"  # the user's income survives too
    assert again["savings_target"] == "6400.00"


async def test_events_items_and_activation(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    plan = (await _generate(client, loaded)).json()
    names = {v: k for k, v in (await _names(client, loaded)).items()}

    resp = await client.post(
        f"/api/v1/plans/{plan['id']}/events",
        json={
            "title": "College fest",
            "amount": "1500",
            "category_id": names["Education"],
            "expected_date": "2026-11-20",
        },
        headers=loaded,
    )
    assert resp.status_code == 201
    with_event = resp.json()
    assert with_event["fit"]["events_total"] == "1500.00"
    assert with_event["fit"]["planned_total"] == "15710.00"

    bad = await client.post(
        f"/api/v1/plans/{plan['id']}/events",
        json={"title": "Trip", "amount": "100", "expected_date": "2026-12-02"},
        headers=loaded,
    )
    assert bad.json()["error"]["code"] == "DATE_OUTSIDE_MONTH"

    added = (
        await client.post(
            f"/api/v1/plans/{plan['id']}/items",
            json={"category_id": names["Health"], "planned_amount": "500"},
            headers=loaded,
        )
    ).json()
    assert any(
        i["category_id"] == names["Health"] and i["source"] == "user" for i in added["items"]
    )
    not_spending = await client.post(
        f"/api/v1/plans/{plan['id']}/items",
        json={"category_id": names["Salary"], "planned_amount": "1"},
        headers=loaded,
    )
    assert not_spending.json()["error"]["code"] == "NOT_A_SPENDING_CATEGORY"

    event_id = with_event["events"][0]["id"]
    resp = await client.delete(f"/api/v1/plans/{plan['id']}/events/{event_id}", headers=loaded)
    assert resp.json()["events"] == []

    active = (await client.post(f"/api/v1/plans/{plan['id']}/activate", headers=loaded)).json()
    assert active["status"] == "active"
    again = await client.post(f"/api/v1/plans/{plan['id']}/activate", headers=loaded)
    assert again.status_code == 409
    regen = await _generate(client, loaded)
    assert regen.json()["error"]["code"] == "PLAN_NOT_DRAFT"

    listed = (await client.get("/api/v1/plans", params={"month": "2026-11"}, headers=loaded)).json()
    assert [p["status"] for p in listed] == ["active"]


async def test_plan_vs_actual_tracking(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    plan = (await _generate(client, loaded, month="2026-10")).json()
    await client.post(f"/api/v1/plans/{plan['id']}/activate", headers=loaded)
    names = await _names(client, loaded)

    body = (
        await client.get(
            "/api/v1/plans/current/tracking", params={"month": "2026-10"}, headers=loaded
        )
    ).json()
    rows = {names.get(r["category_id"], "?"): r for r in body["rows"]}
    assert rows["Rent"]["planned"] == "9000.00"
    assert rows["Rent"]["spent"] == "9000.00"
    assert rows["Rent"]["status"] == "warning"  # 100% used
    assert body["spent_total"] == "15848.00"
    assert body["actual_income"] == "30112.00"
    assert body["days_elapsed"] == 31  # October is over (today is 1 Nov)
    # Netflix was never planned for October: unplanned spending shows up as over.
    assert rows["Subscriptions"]["status"] == "over"

    missing = await client.get(
        "/api/v1/plans/current/tracking", params={"month": "2026-12"}, headers=loaded
    )
    assert missing.status_code == 404


async def test_dismissed_recurring_leaves_the_plan(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    groups = (await client.get("/api/v1/recurring", headers=loaded)).json()["groups"]
    emi = next(g for g in groups if g["merchant"] == "Bajaj Finance")
    resp = await client.patch(
        f"/api/v1/recurring/{emi['id']}", json={"status": "dismissed"}, headers=loaded
    )
    assert resp.json()["status"] == "dismissed"

    plan = (await _generate(client, loaded)).json()
    names = await _names(client, loaded)
    lines = _lines(plan, names)
    assert ("EMI & Loans", "fixed") not in lines
    assert lines[("EMI & Loans", "forecast")] == "2500.00"  # back to ordinary spending

    # Dismissed charges drop out of the monthly recurring total.
    body = (await client.get("/api/v1/recurring", headers=loaded)).json()
    assert body["monthly_total"] == "9000.00"


async def test_self_transfer_pairs_across_own_accounts(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    savings = await create_account(client, auth, name="Savings", last4="1111")
    wallet = await create_account(client, auth, name="Second bank", last4="2222")
    out = b"Date,Narration,Debit,Credit\n10/10/2026,UPI/DR/1/MONEY MOVE/x@ybl,7000.00,\n"
    inn = b"Date,Narration,Debit,Credit\n11/10/2026,NEFT-ABCD0123456-PARENT FUNDS,,7000.00\n"
    mapping = {
        "date_col": "Date",
        "description_col": "Narration",
        "amount_mode": "split",
        "debit_col": "Debit",
        "credit_col": "Credit",
    }
    for account, body in ((savings, out), (wallet, inn)):
        resp = await client.post(
            "/api/v1/uploads",
            headers=auth,
            data={"account_id": account["id"], "source_type": "generic_csv"},
            files={"file": ("s.csv", body, "text/csv")},
        )
        await client.post(
            f"/api/v1/uploads/{resp.json()['id']}/column-mapping", json=mapping, headers=auth
        )
    txns = (await client.get("/api/v1/transactions", headers=auth)).json()["items"]
    assert sorted(t["kind"] for t in txns) == ["self_transfer", "self_transfer"]


async def test_other_users_plan_is_404(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    plan = (await _generate(client, loaded)).json()
    other = await register(client, "b@example.com", "Bala Iyer")
    assert (await client.get(f"/api/v1/plans/{plan['id']}", headers=other)).status_code == 404
    resp = await client.patch(
        f"/api/v1/plans/{plan['id']}", json={"expected_income": "1"}, headers=other
    )
    assert resp.status_code == 404
    item = plan["items"][0]
    resp = await client.patch(
        f"/api/v1/plans/{plan['id']}/items/{item['id']}",
        json={"planned_amount": "1"},
        headers=other,
    )
    assert resp.status_code == 404
    groups = (await client.get("/api/v1/recurring", headers=loaded)).json()["groups"]
    resp = await client.patch(
        f"/api/v1/recurring/{groups[0]['id']}", json={"status": "dismissed"}, headers=other
    )
    assert resp.status_code == 404
