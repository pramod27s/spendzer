import httpx
import pytest

from tests.conftest import register

pytestmark = pytest.mark.anyio


async def test_register_returns_tokens_and_sets_httponly_cookie(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "  Asha@Example.com ", "password": "correct-horse-1", "name": "Asha"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "asha@example.com"
    assert body["user"]["monthly_savings_target_pct"] == "20.00"
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


async def test_register_validation_and_duplicate(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "x@y.co", "password": "short", "name": "X"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    await register(client)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "asha@example.com", "password": "another-pass-9", "name": "A"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_login_and_wrong_password(client: httpx.AsyncClient) -> None:
    await register(client)
    ok = await client.post(
        "/api/v1/auth/login", json={"email": "asha@example.com", "password": "correct-horse-1"}
    )
    assert ok.status_code == 200
    bad = await client.post(
        "/api/v1/auth/login", json={"email": "asha@example.com", "password": "wrong-password"}
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"
    missing = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-1"}
    )
    assert missing.status_code == 401


async def test_me_requires_auth_and_updates_target(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/me")).status_code == 401
    headers = await register(client)
    resp = await client.patch(
        "/api/v1/me", json={"monthly_savings_target_pct": "25"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["monthly_savings_target_pct"] == "25.00"
    bogus = {"Authorization": "Bearer not-a-token"}
    assert (await client.get("/api/v1/me", headers=bogus)).status_code == 401


async def test_refresh_rotates_and_detects_reuse(client: httpx.AsyncClient) -> None:
    await register(client)
    old_refresh = client.cookies.get("spendzer_refresh")
    assert old_refresh

    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    new_refresh = client.cookies.get("spendzer_refresh")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the old (revoked) token is treated as theft: every session ends.
    client.cookies.set("spendzer_refresh", old_refresh, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "REFRESH_REUSED"

    client.cookies.set("spendzer_refresh", new_refresh, path="/api/v1/auth")
    after = await client.post("/api/v1/auth/refresh")
    assert after.status_code == 401


async def test_logout_revokes_refresh(client: httpx.AsyncClient) -> None:
    await register(client)
    token = client.cookies.get("spendzer_refresh")
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.set("spendzer_refresh", token or "", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
