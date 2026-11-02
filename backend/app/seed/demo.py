"""Create (or reset) the shared demo account with ~4 months of realistic, synthetic data.

    python -m app.seed.demo

Everything goes through the real pipeline — statement parsing, categorization, recurring
detection, dedup, plans and alerts — so the demo shows exactly what a real user would see.
Dates are relative to today, so the demo always looks current. Re-running resets it.
"""

import asyncio
import csv
import hashlib
import io
import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.core import clock
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Upload
from app.models.enums import AccountType, UploadStatus
from app.repositories import account_repo, category_repo, merchant_rule_repo, user_repo
from app.schemas.plan import GenerateIn
from app.services import planner_service
from app.services.upload_service import process_upload

DEMO_PASSWORD = "spendzer-demo"
DEMO_NAME = "Asha Verma"
SAVINGS_TARGET = Decimal("20")


@dataclass
class Row:
    day: date
    narration: str
    amount: Decimal
    credit: bool = False


def _months_back(today: date, n: int) -> date:
    idx = today.year * 12 + today.month - 1 - n
    return date(idx // 12, idx % 12 + 1, 1)


def _last_day(month: date) -> date:
    return (_months_back(month, -1)) - timedelta(days=1)


class _Ref:
    """Sequential 12-digit UPI references, so bank and Paytm rows can share them."""

    def __init__(self) -> None:
        self.n = 402918300000

    def next(self) -> str:
        self.n += 7
        return str(self.n)


def _upi(ref: str, payee: str, vpa: str, note: str = "Payment") -> str:
    return f"UPI/DR/{ref}/{payee}/YESB/{vpa}/{note}"


def build_statement(today: date) -> tuple[list[Row], list[tuple[Row, str, str]]]:
    """Bank rows for 3 full months + this month so far, and the UPI payments also made via Paytm."""
    rng = random.Random(f"spendzer-demo-{today.isoformat()}")
    ref = _Ref()
    rows: list[Row] = []
    paytm: list[tuple[Row, str, str]] = []
    start = _months_back(today, 3)

    def add(day: date, narration: str, amount: float, credit: bool = False) -> Row | None:
        if day >= today:  # nothing from the future
            return None
        row = Row(day, narration, Decimal(str(round(amount, 2))), credit)
        rows.append(row)
        return row

    def upi(
        day: date,
        payee: str,
        vpa: str,
        amount: float,
        via_paytm: bool = False,
        note: str = "Payment",
    ) -> None:
        r = ref.next()
        row = add(day, _upi(r, payee.upper(), vpa, note), amount)
        if row and via_paytm:
            paytm.append((row, payee, r))

    month = start
    while month <= today:
        last = min(_last_day(month), today - timedelta(days=1))
        mname = month.strftime("%b")

        def on(d: int, month: date = month) -> date:
            return month.replace(day=min(d, _last_day(month).day))

        add(on(1), f"NEFT-ACMEN{month:%Y%m}0112-ACME TECH PVT LTD-SALARY", 52000, credit=True)
        add(on(3), "ACH D- BAJAJ FINANCE LTD-P400XXXX", 2500)
        upi(on(5), "Ramesh Kumar", "rameshk@oksbi", 12000, note=f"Rent for {mname}")
        add(on(8), "AIRTEL PREPAID RECHARGE 9XXXXXX123", 299)
        add(on(12), "NETFLIX.COM SI 4591XXXXXXXX1234", 649)
        add(on(15), "BESCOM ELECTRICITY BILL BBPS", rng.choice([860, 945, 1120, 990]))
        add(on(20), "SPOTIFY INDIA SI 4591XXXXXXXX1234", 119)
        # A steady shopping baseline, so one unusually big purchase stands out.
        add(on(9), "POS 4591XXXXXXXX1234 AMAZON PAY IN", rng.randrange(600, 1800, 1))
        add(on(24), "POS 4591XXXXXXXX1234 MYNTRA DESIGNS", rng.randrange(700, 2200, 1))

        d = month
        while d <= last:
            roll = rng.random()
            if roll < 0.32:
                payee, vpa = rng.choice([("Swiggy", "swiggy@ybl"), ("Zomato", "zomato@hdfcbank")])
                upi(d, payee, vpa, rng.randrange(180, 650, 10), via_paytm=rng.random() < 0.5)
            if 0.2 < roll < 0.36:
                payee, vpa = rng.choice(
                    [
                        ("Blinkit", "blinkit@ybl"),
                        ("Zepto", "zepto@ybl"),
                        ("Swiggy Instamart", "instamart@ybl"),
                    ]
                )
                upi(d, payee, vpa, rng.randrange(220, 950, 10))
            if rng.random() < 0.45:
                payee, vpa = rng.choice(
                    [
                        ("Uber India", "uber@axisbank"),
                        ("Rapido", "rapido@ybl"),
                        ("Namma Metro", "bmrcl@ybl"),
                    ]
                )
                upi(d, payee, vpa, rng.randrange(40, 320, 5), via_paytm=rng.random() < 0.3)
            if rng.random() < 0.03:
                add(d, "POS 4591XXXXXXXX1234 AMAZON PAY IN", rng.randrange(450, 3200, 1))
            if rng.random() < 0.05:
                upi(d, "Starbucks", "starbucks@hdfcbank", rng.randrange(280, 520, 10))
            if rng.random() < 0.04:
                upi(d, "Raju Stores", "q73519244@ybl", rng.randrange(80, 400, 10))
            d += timedelta(days=1)

        upi(on(22), "Bookmyshow", "bms@icici", rng.randrange(400, 900, 10))
        upi(on(17), "Apollo Pharmacy", "apollo@hdfcbank", rng.randrange(150, 700, 10))
        if month == _months_back(today, 1):
            add(on(19), "POS 4591XXXXXXXX1234 CROMA RETAIL", 8999)  # an unusual purchase
            add(
                on(26),
                f"UPI/CR/{ref.next()}/KIRAN RAO/ICIC/kiranrao@okicici/Splitwise",
                650,
                credit=True,
            )
            add(on(28), "IMPS-612345678901-ASHA VERMA-SBIN-XXXXXXX9876-Savings", 5000)
        if month.month in (3, 6, 9, 12):
            add(_last_day(month), "CREDIT INTEREST CAPITALISED", 214, credit=True)
        month = _months_back(month, -1)

    rows.sort(key=lambda r: r.day)
    return rows, paytm


def bank_csv(rows: list[Row]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Sample Bank Ltd. (synthetic demo statement)"])
    w.writerow([])
    w.writerow(["Date", "Narration", "Withdrawal Amt.", "Deposit Amt."])
    for r in rows:
        amt = f"{r.amount:.2f}"
        w.writerow(
            [
                r.day.strftime("%d/%m/%Y"),
                r.narration,
                "" if r.credit else amt,
                amt if r.credit else "",
            ]
        )
    return buf.getvalue().encode()


def paytm_csv(rows: list[tuple[Row, str, str]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Date",
            "Time",
            "Transaction Details",
            "Other Transaction Details (UPI ID or A/c No)",
            "Your Account",
            "Amount",
            "UPI Ref No.",
            "Order ID",
            "Remarks",
            "Tags",
            "Comment",
        ]
    )
    for row, payee, ref in rows:
        w.writerow(
            [
                row.day.strftime("%d/%m/%Y"),
                "13:05",
                f"Paid to {payee}",
                "",
                "Sample Bank - 21",
                f"-{row.amount:.2f}",
                ref,
                "",
                "",
                "",
                "",
            ]
        )
    return buf.getvalue().encode()


async def _upload(
    user_id: uuid.UUID, account_id: uuid.UUID, source: str, name: str, data: bytes
) -> None:
    async with SessionLocal() as session:
        upload = Upload(
            user_id=user_id,
            account_id=account_id,
            source_type=source,
            file_name=name,
            file_hash=hashlib.sha256(data).hexdigest(),
            status=UploadStatus.PENDING,
        )
        session.add(upload)
        await session.commit()
        upload_id = upload.id
    await process_upload(user_id, upload_id, data)


async def create_demo() -> None:
    settings = get_settings()
    today = clock.today()
    rows, paytm_rows = build_statement(today)

    async with SessionLocal() as session:
        existing = await user_repo.get_by_email(session, settings.demo_email)
        if existing is not None:
            await session.delete(existing)  # everything cascades
            await session.commit()

        user = await user_repo.create(
            session,
            email=settings.demo_email,
            password_hash=hash_password(DEMO_PASSWORD),
            name=DEMO_NAME,
        )
        user.monthly_savings_target_pct = SAVINGS_TARGET
        await account_repo.get_or_create_cash(session, user.id)
        bank = await account_repo.create(
            session,
            user.id,
            name="HDFC Savings",
            type=AccountType.BANK,
            institution="HDFC Bank",
            last4="4321",
            column_mapping={
                "date_col": "Date",
                "description_col": "Narration",
                "amount_mode": "split",
                "debit_col": "Withdrawal Amt.",
                "credit_col": "Deposit Amt.",
                "amount_col": None,
                "type_col": None,
            },
        )
        paytm = await account_repo.create(
            session, user.id, name="Paytm", type=AccountType.UPI, institution="Paytm"
        )
        await account_repo.create(
            session,
            user.id,
            name="SBI Savings",
            type=AccountType.BANK,
            institution="SBI",
            last4="9876",
        )
        # A correction the demo user "taught" Spendzer earlier.
        groceries = await category_repo.get_system_by_name(session, "Groceries")
        if groceries:
            await merchant_rule_repo.upsert_exact(session, user.id, "Raju Stores", groceries.id)
        await session.commit()
        user_id, bank_id, paytm_id = user.id, bank.id, paytm.id

    await _upload(user_id, bank_id, "generic_csv", "hdfc-savings-statement.csv", bank_csv(rows))
    if paytm_rows:
        await _upload(user_id, paytm_id, "paytm", "paytm-upi-statement.csv", paytm_csv(paytm_rows))

    # Last month: planned, tracked and now closed (so there's a month-end review);
    # this month: an active plan with safe-to-spend.
    async with SessionLocal() as session:
        demo_user = await user_repo.get(session, user_id)
        assert demo_user is not None
        for month in (_months_back(today, 1), _months_back(today, 0)):
            plan = await planner_service.generate(session, demo_user, month, GenerateIn())
            await planner_service.activate(session, demo_user, plan.id)
        await planner_service.close_finished_plans(session, demo_user)
    print(f"Demo ready: {settings.demo_email} / {DEMO_PASSWORD}")
    print(f"  {len(rows)} bank rows, {len(paytm_rows)} also in the Paytm export")


if __name__ == "__main__":
    asyncio.run(create_demo())
