import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.seed.demo import DEMO_PASSWORD, build_statement, create_demo

pytestmark = pytest.mark.anyio


def test_database_url_gets_the_async_driver() -> None:
    for url in ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"):
        assert Settings(database_url=url).database_url == "postgresql+asyncpg://u:p@h:5432/db"
    async_url = "postgresql+asyncpg://u:p@h/db"
    assert Settings(database_url=async_url).database_url == async_url


def test_production_refuses_weak_settings() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="change-me-in-env")
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="x" * 48, cookie_secure=False)
    ok = Settings(environment="production", jwt_secret="x" * 48, cookie_secure=True)
    assert ok.is_production


async def test_security_headers(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    resp = await client.get("/api/v1/me", headers=auth)
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["cache-control"] == "no-store"


def test_demo_statement_is_realistic_and_never_in_the_future() -> None:
    from datetime import date

    today = date(2026, 11, 15)
    rows, paytm = build_statement(today)
    assert all(r.day < today for r in rows)
    assert rows[0].day == date(2026, 8, 1)  # three full months before this one
    salaries = [r for r in rows if "SALARY" in r.narration]
    assert len(salaries) == 4  # Aug, Sep, Oct, Nov
    assert paytm and all(any(p[0] is r for r in rows) for p in paytm)
    assert build_statement(today)[0] == rows  # deterministic for a given day


async def test_demo_account_seeds_resets_and_cannot_be_deleted(client: httpx.AsyncClient) -> None:
    await create_demo()
    await create_demo()  # idempotent: resets instead of duplicating

    login = await client.post(
        "/api/v1/auth/login", json={"email": "demo@spendzer.app", "password": DEMO_PASSWORD}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    txns = (await client.get("/api/v1/transactions", params={"size": 200}, headers=headers)).json()
    assert txns["total"] > 100
    assert any(t["dedup_of"] for t in txns["items"])  # Paytm copies counted once
    recurring = (await client.get("/api/v1/recurring", headers=headers)).json()
    assert {"Ramesh Kumar", "Netflix", "Bajaj Finance"} <= {
        g["merchant"] for g in recurring["groups"]
    }
    plans = (await client.get("/api/v1/plans", headers=headers)).json()
    assert {p["status"] for p in plans} == {"active", "closed"}
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any(a["type"] == "anomaly" for a in alerts["alerts"])

    resp = await client.request(
        "DELETE", "/api/v1/me", json={"password": DEMO_PASSWORD}, headers=headers
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "DEMO_ACCOUNT"
