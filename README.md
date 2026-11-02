# Spendzer

**Know where it went, plan where it goes.**

Spendzer turns bank, UPI and card statements into a clear picture of where your money went, then builds next month's budget from your income and tracks it day by day. Built for UPI-first India: amounts in ₹, Indian digit grouping, statements from HDFC, SBI, ICICI, Google Pay, PhonePe, Paytm or any bank's CSV/Excel.

![Dashboard](docs/screenshots/dashboard.png)

**Live demo:** _add your Vercel URL here after deploying_ · demo login `demo@spendzer.app` / `spendzer-demo` (synthetic data)

## What it does

| | |
| --- | --- |
| **Upload anything** | CSV / Excel from any bank (map columns once), PDF statements from HDFC, SBI and ICICI (including password-protected ones), HDFC credit card, and Google Pay, PhonePe and Paytm exports. Raw files are parsed in memory and deleted. |
| **Clean every line** | `UPI/DR/402918374651/SWIGGY/YESB/swiggy@ybl/Payment` → **Swiggy · Food & Dining**. Keyword rules, your own corrections ("apply to all from this merchant?"), and an ML fallback for merchants no rule knows. |
| **Only real money counts** | Refunds, cashback, card bill payments and transfers between your own accounts are kept out of income and spending. A payment that's in both your bank statement and your GPay export is counted once. |
| **See the picture** | Income vs spending, savings rate, category and bucket split, trends, top merchants, daily and weekday patterns, plain-language insight cards. |
| **Plan next month** | Savings come off the top, then recurring costs (rent, EMIs, subscriptions, detected automatically), then forecasts from your last three months. If it doesn't fit, you get suggested cuts, never a quietly lowered savings goal. |
| **Track it** | Safe-to-spend per day, plan vs actual per category, pace warnings, alerts (80% / 100% of budget, unusual payments, price changes, missing salary), and a month-end review. |

| Planner | Month-end review |
| --- | --- |
| ![Planner](docs/screenshots/planner.png) | ![Review](docs/screenshots/month-review.png) |

| Transactions | Dark mode |
| --- | --- |
| ![Transactions](docs/screenshots/transactions.png) | ![Dashboard, dark](docs/screenshots/dashboard-dark.png) |

| Landing | Onboarding | Mobile |
| --- | --- | --- |
| ![Landing](docs/screenshots/landing.png) | ![Onboarding](docs/screenshots/onboarding.png) | <img src="docs/screenshots/mobile-dashboard.png" width="220" alt="Mobile dashboard"> |

## Stack

- **Backend:** FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · PostgreSQL 16 · Alembic · pandas / openpyxl / xlrd · pdfplumber / pikepdf · rapidfuzz · scikit-learn
- **Frontend:** React 18 · Vite · TypeScript · Tailwind v4 · Radix (shadcn-style components) · Recharts · TanStack Query
- **Ops:** Docker Compose locally · Render (API + Postgres) + Vercel (frontend), see [docs/DEPLOY.md](docs/DEPLOY.md) · GitHub Actions CI

## Run it locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22.

```bash
cp .env.example .env              # then set JWT_SECRET
docker compose up -d db           # Postgres on localhost:5433 (+ a spendzer_test DB)

# API
cd backend
uv sync --python 3.12
uv run alembic upgrade head
uv run python -m app.seed.seed    # default categories + keyword rules (idempotent)
uv run python -m app.ml.train     # category model (optional; re-run any time)
uv run python -m app.seed.demo    # demo account demo@spendzer.app / spendzer-demo (optional)
uv run uvicorn app.main:app --port 8000      # API docs at http://localhost:8000/docs

# Web (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to :8000)
```

Or all in containers: `docker compose up` (the API migrates, seeds, trains and builds the demo on start).

### Sample statements

Everything in `backend/tests/fixtures/` is synthetic. Try:

- `bank_split_columns.csv` as **Any bank (CSV / Excel)**: Aug–Oct 2026; the first upload asks you to confirm columns.
- `hdfc_statement_locked.pdf` (password `ASHA1234`) as **HDFC Bank (PDF)**, then `gpay_statement.pdf` as **Google Pay** into a UPI account: shared payments are counted once.

Regenerate the PDFs with `uv run --with reportlab python tests/fixtures/make_pdf_fixtures.py`.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://spendzer:spendzer@localhost:5433/spendzer` | `postgres://` URLs are converted automatically |
| `JWT_SECRET` | none | **Required in production** (32+ chars): `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ENVIRONMENT` | `development` | `production` enforces a strong secret and secure cookies, adds HSTS |
| `COOKIE_SECURE` | `true` | `false` only for plain-http local dev |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list |
| `RATE_LIMIT_ENABLED` | `true` | 5 logins/min/IP, 20 uploads/hour/user |
| `SEED_DEMO` | `false` | container start: (re)create the demo account |

## Tests

```bash
cd backend
uv run pytest --cov=app           # needs the docker db (uses the spendzer_test database)
uv run ruff check . && uv run ruff format --check . && uv run mypy app

cd frontend
npm test && npm run typecheck && npm run build
```

172 backend tests (96% coverage; engine 93–100%, services 87–100%, parsers 88–97%) and 9 frontend tests. CI runs everything on every push ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Build phases

| Phase | Status | Scope |
| --- | --- | --- |
| 1. MVP | ✅ | Auth (JWT + rotating httpOnly refresh cookie), accounts, CSV/Excel upload with column mapping, merchant extraction, rule categorization + learning from corrections, manual cash entries, income / refund / cashback / self-transfer classification, transactions, analytics, dashboard |
| 2. Planner | ✅ | Recurring detection (confirm / dismiss), own-account transfer pairing, per-category forecasts, plan generation with fit check and suggested cuts, one-off events, plan editing + activation, plan vs actual |
| 3. Tracking | ✅ | Safe-to-spend, pace projections, 7 alert types, month-end review, review queue with one-tap answers, insight cards |
| 4. Smarter | ✅ | Bank / card / UPI-app PDF + export parsers, password-protected PDFs, legacy .xls, cross-source dedup, ML categorizer, CSV export, delete account |
| 5. Polish | ✅ | Onboarding, empty states, dark mode, demo account, production hardening, deploy configs, this README. **Live link: pending deploy** |

## Layout

```
backend/app
  api/v1/        routes only: HTTP in, schemas out
  services/      business logic (no HTTP, no SQL)
  repositories/  SQL only; every query filters by user_id
  parsers/       statement parsers (registry: source_type -> parser)
  engine/        pure logic: merchant, categorizer, income, transfers, recurring, dedup,
                 forecast, plan fit, alerts, insights
  ml/            category model (train.py, model.py)
  seed/          default categories, merchant keywords, demo account
frontend/src
  api/  components/  pages/  hooks/  lib/
docs/            DECISIONS.md (choices the spec left open), DEPLOY.md, screenshots/
```

## Privacy

Raw statements are parsed in memory and never stored (a file waiting for its column mapping sits in a private temp file for at most an hour). PDF passwords are used once and never stored or logged. Card numbers are masked to the last four digits before saving. Every query is scoped to the signed-in user. You can export all your data as CSV or delete your account and every row it owns.
