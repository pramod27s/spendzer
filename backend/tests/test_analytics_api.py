import httpx
import pytest

from tests.conftest import create_account, upload_bank_fixture

pytestmark = pytest.mark.anyio

OCTOBER = {"period": "custom", "start": "2026-10-01", "end": "2026-10-31"}


@pytest.fixture
async def loaded(client: httpx.AsyncClient, auth: dict[str, str]) -> dict[str, str]:
    account = await create_account(client, auth)
    await upload_bank_fixture(client, auth, account["id"])
    return auth


async def test_summary_counts_only_income_and_expense(
    client: httpx.AsyncClient, loaded: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/analytics/summary", params=OCTOBER, headers=loaded)
    assert resp.status_code == 200
    body = resp.json()
    # Salary 30,000 + interest 112. Refund, cashback, self-transfer and the unknown
    # credit don't count.
    assert body["income"] == "30112.00"
    assert body["spending"] == "15848.00"
    assert body["net_savings"] == "14264.00"
    assert body["savings_rate"] == "47.4"
    assert body["period"]["label"] == "October 2026"
    assert body["previous"]["spending"] == "11880.00"
    assert body["has_data"] is True
    assert body["latest_txn_date"] == "2026-10-31"


async def test_category_and_bucket_split(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    body = (await client.get("/api/v1/analytics/categories", params=OCTOBER, headers=loaded)).json()
    split = {c["name"]: c["amount"] for c in body["categories"]}
    assert split == {
        "Rent": "9000.00",
        "EMI & Loans": "2500.00",
        "Shopping": "1299.00",
        "Food & Dining": "1070.00",
        "Groceries": "780.00",
        "Subscriptions": "649.00",
        "Other": "320.00",
        "Transport": "230.00",
    }
    assert body["categories"][0]["name"] == "Rent"
    assert body["categories"][0]["pct"] == "56.8"
    buckets = {b["bucket"]: b["amount"] for b in body["buckets"]}
    assert buckets == {"fixed": "12149.00", "variable": "1010.00", "discretionary": "2689.00"}


async def test_trend_fills_months(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    body = (
        await client.get(
            "/api/v1/analytics/trend",
            params={"months": 4, "end_month": "2026-10-01"},
            headers=loaded,
        )
    ).json()
    assert [(p["month"], p["income"], p["spending"]) for p in body["points"]] == [
        ("2026-07", "0.00", "0.00"),
        ("2026-08", "30000.00", "12570.00"),
        ("2026-09", "30000.00", "11880.00"),
        ("2026-10", "30112.00", "15848.00"),
    ]


async def test_top_merchants(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    params = {"period": "custom", "start": "2026-08-01", "end": "2026-10-31", "limit": 3}
    body = (await client.get("/api/v1/analytics/merchants", params=params, headers=loaded)).json()
    assert [(m["merchant"], m["amount"], m["count"]) for m in body["merchants"]] == [
        ("Ramesh Kumar", "27000.00", 3),
        ("Bajaj Finance", "7500.00", 3),
        ("Amazon", "1299.00", 1),
    ]


async def test_daily_and_weekday(client: httpx.AsyncClient, loaded: dict[str, str]) -> None:
    body = (await client.get("/api/v1/analytics/daily", params=OCTOBER, headers=loaded)).json()
    assert len(body["days"]) == 31
    day = {d["date"]: d["amount"] for d in body["days"]}
    assert day["2026-10-05"] == "9000.00"
    assert day["2026-10-15"] == "0.00"  # self-transfer isn't spending
    assert len(body["weekdays"]) == 7


async def test_empty_account_has_no_data(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    body = (await client.get("/api/v1/analytics/summary", headers=auth)).json()
    assert body["has_data"] is False
    assert body["savings_rate"] is None
    assert body["spending"] == "0.00"


async def test_invalid_custom_period(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    resp = await client.get("/api/v1/analytics/summary", params={"period": "custom"}, headers=auth)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PERIOD"
