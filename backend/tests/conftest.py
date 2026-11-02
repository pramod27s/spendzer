import os
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import Any

# Configure before the app (and its engine) is imported.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://spendzer:spendzer@localhost:5433/spendzer_test"
)
os.environ["DATABASE_NULL_POOL"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["COOKIE_SECURE"] = "false"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789"

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed.seed import seed  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def _schema() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed(session)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sample statement covers Aug–Oct 2026; pin "today" just after it."""
    monkeypatch.setattr("app.core.clock.today", lambda: date(2026, 11, 1))


@pytest.fixture(autouse=True)
def _no_ml_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests don't depend on a locally trained model file; ML tests train their own."""
    monkeypatch.setattr("app.services.enrichment.get_model", lambda: None)


@pytest.fixture
async def client(_schema: None) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # Cascades to every user-owned row; system categories and global rules survive.
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))


async def register(
    client: httpx.AsyncClient, email: str = "asha@example.com", name: str = "Asha Verma"
) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "name": name},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def auth(client: httpx.AsyncClient) -> dict[str, str]:
    return await register(client)


async def create_account(
    client: httpx.AsyncClient, headers: dict[str, str], **overrides: Any
) -> dict[str, Any]:
    body = {"name": "Savings", "type": "bank", "institution": "Sample Bank", "last4": "4321"}
    body.update(overrides)
    resp = await client.post("/api/v1/accounts", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


async def upload_file(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    account_id: str,
    path: Path,
    content_type: str = "text/csv",
) -> httpx.Response:
    return await client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"account_id": account_id, "source_type": "generic_csv"},
        files={"file": (path.name, path.read_bytes(), content_type)},
    )


SPLIT_MAPPING = {
    "date_col": "Date",
    "description_col": "Narration",
    "amount_mode": "split",
    "debit_col": "Withdrawal Amt.",
    "credit_col": "Deposit Amt.",
}


async def upload_bank_fixture(
    client: httpx.AsyncClient, headers: dict[str, str], account_id: str
) -> dict[str, Any]:
    resp = await upload_file(client, headers, account_id, FIXTURES / "bank_split_columns.csv")
    assert resp.status_code == 202, resp.text
    upload_id = resp.json()["id"]
    status = (await client.get(f"/api/v1/uploads/{upload_id}", headers=headers)).json()
    if status["status"] == "needs_mapping":
        resp = await client.post(
            f"/api/v1/uploads/{upload_id}/column-mapping", json=SPLIT_MAPPING, headers=headers
        )
        assert resp.status_code == 202, resp.text
        status = (await client.get(f"/api/v1/uploads/{upload_id}", headers=headers)).json()
    assert status["status"] == "done", status
    return dict(status)
