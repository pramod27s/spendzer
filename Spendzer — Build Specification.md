# Spendzer — Build Specification

Nov 1, 2026 · @Pramod

## Overview

Spendzer is a personal finance web app that turns uploaded bank, UPI and card statements into a clear picture of where money went, then builds a budget plan for next month from the user's income.

**Tagline:** know where it went, plan where it goes.

**Problem.** Spending through UPI, cards and auto-debits is invisible. Users don't know how their money is split across categories, so they can't plan or save deliberately.

**Goals**

1. Ingest real statements (CSV, Excel, PDF) from Indian banks, UPI apps and credit cards with minimal manual work.
2. Categorize every transaction automatically and learn from user corrections.
3. Show how income and spending divide across categories and over time.
4. Generate a next-month budget plan from income, fixed costs, past behaviour and a savings target.
5. Track the plan during the month and review it at month end.

**Target user.** An individual in India (students and early-career earners first), single user per account, amounts in INR.

**How to use this doc with Claude.** This is the full build spec. Build phase by phase as listed under Build phases, finishing and testing each phase before the next. Where this doc is silent, choose the simplest option and note the decision in `docs/DECISIONS.md`.

## Core loop and features

Everything in Spendzer serves one monthly loop: **income in → analyze past months → plan next month → track during the month → review → plan again.**

&#91;embedded content: Spendzer monthly loop · 6 stages\]

Uploads drive analysis; the plan is the center of the loop, and each review's actuals sharpen the next forecast.

| # | Feature | What it does | Phase |
| --- | --- | --- | --- |
| 1 | Auth | Register, login, JWT access + refresh tokens | 1 |
| 2 | Statement upload | Upload CSV / Excel / PDF; pick source (bank, UPI app, card) | 1 (CSV), 2 (PDF) |
| 3 | Parsing + normalization | Convert every source into one `Transaction` shape | 1 |
| 4 | Merchant extraction | Clean UPI / NEFT / POS narrations into a merchant name | 1 |
| 5 | Rule-based categorization | Keyword map + user overrides | 1 |
| 6 | Manual entry | Add cash spends and cash income | 1 |
| 7 | Income detection | Flag credits as income, refund, cashback, self-transfer | 1 |
| 8 | Past-month analysis | Category split, trends, top merchants, savings rate | 1 |
| 9 | Recurring detection | Find subscriptions, rent, EMIs | 2 |
| 10 | Next-month planner | Build a budget from income, savings target, fixed costs, history | 2 |
| 11 | Planned one-off events | Fees, trips, gifts added to a month's plan | 2 |
| 12 | Plan vs actual | Per-category progress during the month | 2 |
| 13 | Safe-to-spend | Daily allowance = remaining discretionary budget ÷ days left | 3 |
| 14 | Alerts | 80% / 100% of a category, pace warnings, anomalies | 3 |
| 15 | Month-end review | Planned vs actual, savings hit or missed, feeds next plan | 3 |
| 16 | Cross-source dedup | Same payment in bank + UPI statements counted once | 4 |
| 17 | ML categorizer | Classifier for merchants the rules don't know | 4 |

Out of scope for v1: live bank connections (Account Aggregator), SMS reading, multi-user households, investments tracking, non-INR currencies.

## Tech stack

The whole backend is Python FastAPI; the frontend is React.

| Layer | Choice | Notes |
| --- | --- | --- |
| Backend framework | FastAPI (Python 3.12) | Async routes, auto OpenAPI docs at `/docs` |
| Validation | Pydantic v2 | Request/response schemas, settings via `pydantic-settings` |
| ORM + migrations | SQLAlchemy 2.0 + Alembic | Typed models, versioned schema |
| Database | PostgreSQL 16 | Relational data, heavy `GROUP BY` aggregation |
| Auth | `PyJWT` + `passlib[bcrypt]` | Access token 15 min, refresh token 7 days |
| CSV / Excel | `pandas` + `openpyxl` | Also used for all analytics |
| PDF | `pdfplumber` (tables), `pikepdf` (password-protected files) |  |
| ML (phase 4) | `scikit-learn` | TF-IDF + Logistic Regression, saved with `joblib` |
| Background jobs | FastAPI `BackgroundTasks` first; Celery + Redis if parsing exceeds \~5 s |  |
| Frontend | React 18 + Vite + TypeScript |  |
| UI | Tailwind CSS + shadcn/ui |  |
| Charts | Recharts |  |
| Data fetching | TanStack Query + Axios |  |
| Testing | `pytest` + `httpx`, Vitest on frontend |  |
| Dev setup | Docker Compose (api, db, frontend) |  |
| Deployment | Render / Railway for API + Postgres, Vercel for frontend |  |

## Architecture and project structure

One FastAPI service with layered code: routes call services, services call repositories and the parser / categorizer / planner modules. No business logic in routes.

Monorepo layout:

```
spendzer/
  docker-compose.yml
  .env.example
  docs/DECISIONS.md
  backend/
    pyproject.toml
    alembic/
    app/
      main.py                 # app factory, CORS, router registration
      core/                   # config.py, security.py, db.py, deps.py
      models/                 # SQLAlchemy tables (one file per table)
      schemas/                # Pydantic request/response models
      api/v1/                 # auth, uploads, transactions, categories,
                              # income, analytics, plans, budgets, alerts
      repositories/           # DB queries only
      services/               # upload_service, analytics_service,
                              # planner_service, tracking_service
      parsers/
        base.py               # BaseParser + ParsedTransaction
        registry.py           # source_type -> parser class
        generic_csv.py        # column-mapping CSV/Excel parser
        hdfc_pdf.py, sbi_pdf.py, icici_csv.py, ...
        gpay.py, phonepe.py, paytm.py
      engine/
        merchant.py           # narration -> merchant name
        categorizer.py        # rules + overrides + ML fallback
        income.py             # credit classification
        recurring.py          # recurring detection
        dedup.py              # duplicate + self-transfer detection
        forecast.py           # per-category prediction
      ml/                     # train.py, model.joblib
      seed/                   # default categories + merchant keywords
    tests/
      fixtures/               # sample statements (anonymized)
  frontend/
    src/
      api/  components/  pages/  hooks/  lib/
```

## Database schema

PostgreSQL, UUID primary keys, `created_at` / `updated_at` on every table. Money is stored as `NUMERIC(12,2)` in INR, never float. Every user-owned row has `user_id` and every query filters by it.

| Table | Key columns | Notes |
| --- | --- | --- |
| `users` | id, email (unique), password\_hash, name, monthly\_savings\_target\_pct, created\_at |  |
| `accounts` | id, user\_id, name, type (`bank` / `upi` / `card` / `cash`), institution, last4 | Lets self-transfers between own accounts be detected |
| `uploads` | id, user\_id, account\_id, source\_type, file\_name, file\_hash, status (`pending` / `parsing` / `done` / `failed`), error, txn\_count, period\_start, period\_end | `file_hash` blocks re-uploading the same file |
| `transactions` | id, user\_id, account\_id, upload\_id (nullable for manual), txn\_date, amount, direction (`debit` / `credit`), raw\_description, merchant, category\_id, kind, is\_recurring, recurring\_group\_id, dedup\_of (nullable), categorized\_by (`rule` / `override` / `ml` / `user`), note | Index on (user\_id, txn\_date) and (user\_id, category\_id) |
| `categories` | id, user\_id (null = system default), name, bucket (`fixed` / `variable` / `discretionary` / `income` / `excluded`), icon, color |  |
| `merchant_rules` | id, user\_id (null = global), pattern, match\_type (`contains` / `regex` / `exact`), category\_id, priority | User rules beat global rules |
| `recurring_groups` | id, user\_id, merchant, category\_id, typical\_amount, typical\_day, frequency (`monthly` / `weekly` / `yearly`), active |  |
| `monthly_plans` | id, user\_id, month (first day of month), expected\_income, savings\_target, status (`draft` / `active` / `closed`) | Unique (user\_id, month) |
| `plan_items` | id, plan\_id, category\_id, planned\_amount, bucket, source (`fixed` / `forecast` / `user`) |  |
| `planned_events` | id, plan\_id, title, amount, category\_id, expected\_date | One-off expenses |
| `alerts` | id, user\_id, type, message, category\_id, month, read, created\_at |  |

`transactions.kind` values: `expense`, `income`, `refund`, `cashback`, `self_transfer`, `investment`, `unknown`. Only `expense` counts as spending; only `income` counts as income.

Default categories to seed: Food & Dining, Groceries, Transport, Fuel, Shopping, Entertainment, Subscriptions, Rent, Utilities, Mobile & Internet, Education, Health, Personal Care, Travel, EMI & Loans, Gifts & Donations, Fees & Charges, Other; income categories Salary, Stipend, Pocket Money, Freelance, Interest, Other Income; excluded categories Self Transfer, Investment, Refund.

## Statement ingestion and parsing

Every upload runs the same pipeline; only the parser differs per source.

1. **Upload.** `POST /uploads` with file, `account_id`, `source_type` and optional PDF password. Accept `.csv`, `.xlsx`, `.xls`, `.pdf` up to 10 MB. Compute SHA-256 `file_hash`; reject duplicates with 409.
2. **Queue.** Create `uploads` row with `status=pending`, return 202 with the upload id, run parsing in a background task. Frontend polls `GET /uploads/{id}`.
3. **Decrypt (PDF).** Open with `pikepdf` using the password if given. Wrong password → `status=failed`, error `PDF_PASSWORD_REQUIRED`. Never store or log the password.
4. **Parse.** `registry.get(source_type)` returns a `BaseParser` subclass. It yields `ParsedTransaction(txn_date, amount, direction, raw_description, balance=None)`.
5. **Normalize.** Amount always positive with a separate `direction`; dates as `date`; trim whitespace; drop opening/closing balance rows and empty rows.
6. **Enrich.** Run merchant extraction, income classification, categorization, self-transfer and duplicate checks (later sections).
7. **Save.** Bulk insert in one DB transaction. Update upload with `status=done`, `txn_count`, `period_start`, `period_end`.
8. **Post-process.** Re-run recurring detection for the user and refresh alerts for the affected months.
9. **Delete the raw file** once parsing ends, success or failure.

**Parser contract**

```python
class BaseParser(ABC):
    source_type: ClassVar[str]

    @abstractmethod
    def can_parse(self, file_bytes: bytes, filename: str) -> bool: ...

    @abstractmethod
    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]: ...
```

**Parsers to build**

- `generic_csv`: the user maps columns once (date, description, debit, credit or amount + type), mapping saved per account. This covers any bank on day one.
- Bank-specific PDF parsers for HDFC, SBI, ICICI, Axis, Kotak, added one at a time. Use `pdfplumber` table extraction; fall back to line regex when tables don't detect.
- UPI app exports: GPay, PhonePe, Paytm.
- Credit card PDFs: start with one issuer.

**Date and amount formats to handle:** `dd/mm/yyyy`, `dd-mm-yy`, `dd MMM yyyy`; amounts with commas (`1,23,456.00`), `Dr`/`Cr` suffixes, separate debit/credit columns, and negative numbers.

**Merchant extraction** (`engine/merchant.py`) turns narrations into a clean merchant:

| Raw narration | Merchant |
| --- | --- |
| `UPI/DR/402918374651/SWIGGY/YESB/swiggy@ybl/Payment` | Swiggy |
| `UPI-ZOMATO LTD-zomato@hdfcbank-HDFC0000001-4029...` | Zomato |
| `POS 4591XXXXXXXX1234 AMAZON PAY IN` | Amazon |
| `NEFT-HDFCN52026110112-ACME TECH PVT LTD-SALARY` | Acme Tech (Salary) |
| `ACH D- BAJAJ FINANCE LTD-P400XXXX` | Bajaj Finance |

Steps: split on `/`, `-` and spaces; drop known tokens (UPI, DR, CR, NEFT, IMPS, POS, ACH, bank codes, IFSC, long digit runs, VPA domains); take the payee segment; title-case; map aliases (`swiggy instamart` → Swiggy Instamart). Keep the raw narration untouched.

## Categorization engine

Each transaction is categorized by the first layer that matches, and the layer is stored in `categorized_by`.

1. **User override** — a `merchant_rules` row with this `user_id` matching the merchant. Highest priority.
2. **Global rules** — seeded keyword map (`user_id` null), ordered by `priority`.
3. **ML fallback** (phase 4) — classifier prediction, accepted only if confidence ≥ 0.6.
4. **Uncategorized** — category Other, flagged for review in the UI.

**Learning from corrections.** When the user changes a transaction's category, ask: "Apply to all transactions from *Raju Stores*?" If yes, create a user `merchant_rules` row (`exact` match on merchant) and recategorize all that user's past transactions from that merchant except ones set by hand (`categorized_by = user`).

**Seed keyword map (starter, extend in `seed/merchant_keywords.yaml`)**

| Category | Keywords |
| --- | --- |
| Food & Dining | swiggy, zomato, dominos, mcdonald, kfc, starbucks, cafe, restaurant, eatclub |
| Groceries | blinkit, zepto, bigbasket, instamart, dmart, more retail, jiomart |
| Transport | uber, ola, rapido, namma metro, bmtc, irctc, redbus |
| Fuel | petrol, hpcl, bpcl, indian oil, shell |
| Shopping | amazon, flipkart, myntra, ajio, meesho, nykaa |
| Subscriptions | netflix, spotify, hotstar, prime video, youtube premium, apple.com, google play |
| Mobile & Internet | airtel, jio, vi, act fibernet, recharge |
| Utilities | bescom, electricity, bwssb, water, gas, indane |
| Entertainment | bookmyshow, pvr, inox, steam |
| Health | pharmacy, apollo, 1mg, pharmeasy, hospital, clinic |
| Education | udemy, coursera, college, university, fees |
| EMI & Loans | emi, bajaj finance, loan, ach d |
| Fees & Charges | charges, gst on, sms alert, annual fee, penalty |

**ML classifier (phase 4).** Input text = merchant + raw description, lowercased. Pipeline: `TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5))` + `LogisticRegression`. Train on rule-categorized and user-corrected transactions across all users (anonymized merchant text only). Retrain via a script, not on every request. Store model version on predictions.

## Income, recurring, duplicates and self-transfers

These four checks decide what counts as real income and real spending; getting them wrong breaks every number downstream.

**Income classification** (`engine/income.py`), applied to every credit in order:

1. Matches a user's own account (name or last4) → `self_transfer`.
2. Contains refund / reversal / reversed / rev, or equals a recent debit amount from the same merchant within 30 days → `refund`.
3. Contains cashback / reward / cb → `cashback`.
4. Contains salary / sal / stipend / payroll, or is NEFT/IMPS from the same sender within ±3 days of the same day each month → `income` (Salary or Stipend).
5. Interest credit → `income` (Interest).
6. Anything else → `unknown`, shown in an "Is this income?" review queue. The user's answer creates a rule for that sender.

**Self-transfer detection.** A debit in account A and a credit of the same amount in account B, both owned by the user, within 2 days → both marked `self_transfer` and excluded from spending and income. Also catch transfers to the user's own name in the narration and credit card bill payments (the card's individual purchases are the spending, not the bill).

**Recurring detection** (`engine/recurring.py`), run after each upload:

- Group debits by merchant.
- A group is recurring if it has ≥ 3 occurrences, intervals of 28–33 days (monthly) or 6–8 days (weekly), and amounts within ±10% of the median.
- Save a `recurring_groups` row with typical amount (median), typical day of month, frequency; mark its transactions `is_recurring`.
- Mark the group inactive if the expected next charge is 10+ days overdue.

**Cross-source dedup** (`engine/dedup.py`). The same UPI payment appears in the bank statement and the GPay export. Treat two transactions as duplicates when they are from different uploads, same direction, same amount, dates within 1 day, and merchant similarity ≥ 0.8 (`rapidfuzz` token-set ratio). Keep the bank row (it's authoritative), set `dedup_of` on the other, and exclude rows with `dedup_of` from all totals. If a UPI reference number exists in both, match on it directly.

## Analytics

All analytics read only `kind = expense` (spending) and `kind = income` (income), excluding rows with `dedup_of` set. Compute in SQL where possible, pandas for the rest.

| Metric | Definition | Shown as |
| --- | --- | --- |
| Total income | Sum of income in the period | KPI card |
| Total spending | Sum of expenses in the period | KPI card |
| Net savings | Income − spending | KPI card |
| Savings rate | Net savings ÷ income × 100 | KPI card, red below 10% |
| Category split | Spending per category and % of total | Donut chart + table |
| Bucket split | Spending by fixed / variable / discretionary, and % of income | Stacked bar |
| Monthly trend | Income, spending, savings for last 6–12 months | Line chart |
| Category trend | One category's spending per month | Line chart on category page |
| Top merchants | Top 10 merchants by spend, with count | Ranked list |
| Daily spending | Spend per day of the month | Bar chart / calendar heatmap |
| Day-of-week pattern | Average spend per weekday | Bar chart |
| Average transaction | Mean and median per category | Table |
| Anomalies | Category spend > 1.5 × its median of last 3 months | Insight card |

**Insight cards.** Generate 3–5 short, plain-language insights per month, ranked by rupee impact, for example: "Food delivery was ₹4,200 this month, 2.1× your usual" or "Subscriptions cost ₹1,150 a month — 3 services". Each insight is a template plus numbers; no LLM required.

**Period filters:** this month, last month, last 3 / 6 / 12 months, custom range; optional account filter.

## Planning engine (next month)

The planner takes savings out first, then fits spending into what's left. `POST /plans/generate?month=YYYY-MM` creates a `draft` plan the user edits and then activates.

**Algorithm** (`services/planner_service.py`)

1. **Expected income.** Default = median monthly income over the last 3 months with data; the user can override. If no history, require the user to enter it.
2. **Savings target.** `expected_income × user.monthly_savings_target_pct` (default 20%), editable per plan.
3. **Spendable.** `expected_income − savings_target`.
4. **Fixed costs.** One `plan_item` per active recurring group, amount = its typical amount, `source = fixed`.
5. **One-off events.** Sum of `planned_events` for the month, added to their categories.
6. **Forecast variable and discretionary categories.** For each category with spending in the last 3 months, excluding recurring transactions: forecast = median of the 3 monthly totals. Use a weighted mean (0.5, 0.3, 0.2, newest first) when at least one month has zero, and ignore a month flagged as an outlier (> 2 × the median of the others).
7. **Fit check.** `gap = (fixed + events + forecasts) − spendable`.
8. **If gap > 0, suggest cuts** from discretionary categories only, largest first, never below 50% of their forecast; then variable categories, never below 80%. Fixed costs are never cut. Show each cut as a suggestion ("Reduce Food & Dining by ₹1,200").
9. **If the gap still remains**, show a warning with two options: lower the savings target or accept a shortfall.
10. **If gap < 0 (surplus)**, offer to move the surplus to savings or to a buffer category.
11. The user edits any amount, then `POST /plans/{id}/activate` sets `status = active`. Only one active plan per month.

**Worked example**

| Line | Amount (₹) |
| --- | --- |
| Expected income | 30,000 |
| Savings target (20%) | 6,000 |
| Spendable | 24,000 |
| Fixed: rent 9,000 + mobile 299 + subscriptions 650 | 9,949 |
| One-off: college event | 1,500 |
| Forecast: groceries 3,000, transport 2,200, food 5,800, shopping 3,000 | 14,000 |
| Total planned | 25,449 |
| Gap | 1,449 over |
| Suggested cuts: food −1,000, shopping −449 | balanced |

**Rules for the planner**

- Never produce a plan where the savings target is silently reduced; the user must choose that.
- Every number shows where it came from ("median of Aug–Oct") in the UI tooltip.
- Re-generating a draft overwrites only items with `source` `fixed` or `forecast`, never `user` edits.

## Tracking, alerts and month-end review

During the active month the dashboard answers one question: am I on track?

**Plan vs actual.** Per plan item: planned, spent so far, remaining, % used. Progress bar green below 80%, amber 80–100%, red above 100%.

**Safe-to-spend today.**

```latex
\text{safe\_to\_spend} = \frac{\text{discretionary planned} + \text{variable planned} - \text{spent so far in those}}{\text{days left in month, including today}}
```

Floor at 0. Show it as the largest number on the dashboard.

**Pace projection.** For each variable or discretionary category: `projected = spent_so_far ÷ days_elapsed × days_in_month`. If projected > planned × 1.1 and at least 7 days have passed, raise a pace warning.

**Alerts** (generated after each upload or manual entry; no duplicates per type, category and month):

| Type | Trigger | Example message |
| --- | --- | --- |
| `budget_80` | Category reaches 80% of plan | Food & Dining is at 82% with 12 days left |
| `budget_100` | Category exceeds plan | Shopping is ₹640 over budget |
| `pace` | Pace projection rule above | At this pace, Transport ends ₹900 over |
| `anomaly` | Single transaction > 3× category median | ₹6,499 at Croma is unusual for Shopping |
| `recurring_change` | Recurring charge amount changes > 10% | Netflix went from ₹199 to ₹249 |
| `income_missing` | Expected salary/stipend not seen 5 days after its usual day | Stipend hasn't arrived yet this month |
| `stale_data` | No upload for 10 days in the active month | Upload a statement to keep tracking accurate |

In-app only for v1 (a bell with unread count); email optional later.

**Month-end review** (`GET /plans/{id}/review`, plan becomes `closed` on the 1st of next month):

- Planned vs actual income, spending and savings.
- Per category: planned, actual, difference, and over/under label.
- Savings goal hit or missed, by how much.
- Top 3 overspends and top 3 wins.
- Three insight cards.
- Button: "Plan next month", which calls the generator; the forecast already includes this month's actuals.

## API endpoints

All under `/api/v1`, JSON, JWT bearer auth except register/login/refresh. List endpoints paginate with `page` and `size` (default 50, max 200). Errors use `{"error": {"code": "...", "message": "..."}}`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Returns access + refresh tokens |
| POST | `/auth/refresh` | New access token |
| GET / PATCH | `/me` | Profile, savings target % |
| GET / POST / PATCH / DELETE | `/accounts` | Manage bank, UPI, card, cash accounts |
| POST | `/uploads` | Multipart upload (file, account\_id, source\_type, pdf\_password?) → 202 |
| GET | `/uploads`, `/uploads/{id}` | Upload history and status |
| DELETE | `/uploads/{id}` | Remove an upload and its transactions |
| POST | `/uploads/{id}/column-mapping` | Save mapping for generic CSV |
| GET | `/transactions` | Filter by date range, category, account, kind, merchant, search, min/max amount |
| POST | `/transactions` | Manual entry |
| PATCH | `/transactions/{id}` | Change category, kind, note; `apply_to_merchant` flag creates a rule |
| DELETE | `/transactions/{id}` | Delete (manual entries only) |
| GET | `/transactions/review` | Uncategorized + unknown credits queue |
| GET / POST / PATCH / DELETE | `/categories` | System + user categories |
| GET / POST / DELETE | `/merchant-rules` | User rules |
| GET | `/recurring` | Detected recurring groups; PATCH to confirm or dismiss |
| GET | `/analytics/summary` | KPIs for a period |
| GET | `/analytics/categories` | Category and bucket split |
| GET | `/analytics/trend` | Monthly income/spending/savings |
| GET | `/analytics/merchants` | Top merchants |
| GET | `/analytics/daily` | Daily and weekday spending |
| GET | `/analytics/insights` | Insight cards |
| POST | `/plans/generate?month=YYYY-MM` | Create or refresh a draft plan |
| GET | `/plans`, `/plans/{id}` | Plans with items, events, fit check, suggestions |
| PATCH | `/plans/{id}` | Expected income, savings target |
| PATCH | `/plans/{id}/items/{item_id}` | Edit planned amount |
| POST / DELETE | `/plans/{id}/events` | One-off events |
| POST | `/plans/{id}/activate` | Make active |
| GET | `/plans/current/tracking` | Plan vs actual, safe-to-spend, pace |
| GET | `/plans/{id}/review` | Month-end review |
| GET | `/alerts`; PATCH `/alerts/{id}/read` | Alerts |
| GET | `/export/transactions.csv` | Export user data |
| DELETE | `/me` | Delete account and all data |

## Frontend pages

Mobile-first responsive web app; sidebar on desktop, bottom nav on mobile. Amounts formatted in Indian style (`₹1,23,456`) with `Intl.NumberFormat('en-IN')`.

| Page | Route | Contents |
| --- | --- | --- |
| Landing | `/` | Tagline, what it does, sign up |
| Login / Register | `/login`, `/register` | Forms with validation |
| Onboarding | `/onboarding` | Add first account, set savings target %, upload first statement |
| Dashboard | `/dashboard` | Safe-to-spend, income / spent / saved KPIs, plan vs actual bars, category donut, recent transactions, alerts |
| Upload | `/upload` | Drag-and-drop, account + source picker, PDF password field, progress, column-mapping step for generic CSV, upload history |
| Transactions | `/transactions` | Filterable table, inline category change with "apply to merchant" prompt, manual-entry modal |
| Review queue | `/review` | Uncategorized items and "Is this income?" credits, one-tap answers |
| Analytics | `/analytics` | Period filter, category split, bucket split, monthly trend, top merchants, daily heatmap, insight cards |
| Planner | `/plan/:month` | Income + savings inputs, fixed / variable / discretionary sections with editable amounts, one-off events, fit check bar, suggested cuts, Activate button |
| Review | `/review/:month` | Month-end review |
| Recurring | `/recurring` | Subscriptions and EMIs with monthly total, confirm / dismiss |
| Settings | `/settings` | Profile, accounts, categories, merchant rules, export, delete account |

**Shared components:** `KpiCard`, `CategoryDonut`, `TrendLine`, `BudgetProgress`, `SafeToSpendCard`, `InsightCard`, `TransactionTable`, `CategoryPicker`, `MoneyInput`, `UploadDropzone`, `AlertBell`, `EmptyState`.

**UX rules:** every chart has an empty state that points to Upload; every number on the planner has a tooltip explaining its source; category colours are consistent across all charts; dark mode supported.

## Security and privacy

This app holds a user's complete financial history, so treat every rule below as required, not optional.

- **Passwords:** bcrypt via passlib; minimum 8 characters.
- **Tokens:** short-lived access token; refresh token in an httpOnly, Secure, SameSite=Strict cookie; rotate on refresh.
- **Authorization:** every repository query filters by `user_id` from the token. Write a test that user B gets 404 on user A's upload, transaction and plan.
- **Raw files:** processed in memory or a temp dir and deleted right after parsing; never stored in the DB or object storage.
- **PDF passwords:** used once to decrypt, never stored, never logged.
- **Sensitive fields:** mask account numbers to last 4 before saving; strip full card numbers from `raw_description` (regex for 12–19 digit runs → keep last 4).
- **Logging:** never log request bodies on upload, transaction or auth routes; log upload ids, not file contents.
- **Uploads:** check MIME type and extension, 10 MB limit, reject macros in Excel (`openpyxl` with `keep_vba=False`).
- **Rate limiting:** `slowapi` — 5 login attempts per minute per IP, 20 uploads per hour per user.
- **CORS:** only the frontend origin.
- **Secrets:** from environment variables via `pydantic-settings`; `.env` in `.gitignore`; `.env.example` committed.
- **HTTPS** everywhere in production.
- **Data rights:** export all data as CSV; delete account removes every row for that user.
- **Test data:** fixtures must be anonymized — no real names, account numbers or VPAs committed to git.

## Testing, deployment and build phases

**Testing**

- Unit tests for every parser (one anonymized fixture file per source), merchant extraction (table of narration → merchant cases), categorizer, income classifier, recurring detection, dedup, forecast and planner.
- Planner tests must cover: no history, surplus, gap fixed by cuts, gap that cuts can't fix, user edits preserved on regenerate.
- API tests with `httpx.AsyncClient` against a test Postgres (Docker), including the cross-user access test.
- Target ≥ 80% coverage on `engine/` and `services/`.
- GitHub Actions: lint (`ruff`), type check (`mypy`), tests on every push.

**Deployment**

- `docker-compose up` runs api, db and frontend locally; `alembic upgrade head` on start.
- Production: API + Postgres on Render or Railway, frontend on Vercel, env vars set in each dashboard.
- Seed script loads default categories and merchant keywords; idempotent.

**Build phases**

| Phase | Scope | Done when |
| --- | --- | --- |
| 1. MVP | Project setup, Docker, auth, accounts, generic CSV upload with column mapping, merchant extraction, rule categorization, manual entry, income classification, transactions page, analytics (summary, categories, trend, merchants) | User uploads a CSV and sees where the money went |
| 2. Planner | Recurring detection, self-transfer detection, forecast, plan generation, planned events, plan editing and activation, plan vs actual | User generates and activates next month's plan |
| 3. Tracking | Safe-to-spend, pace projection, alerts, month-end review, review queue, insight cards | User tracks a month and gets a review |
| 4. Smarter | Bank PDF parsers (HDFC, SBI, ICICI first), UPI app parsers, cross-source dedup, ML categorizer, export, delete account | Two sources upload without double counting |
| 5. Polish | Onboarding, dark mode, empty states, deployment, README with screenshots and demo account | Live demo link works |

**Instructions for Claude (the builder)**

1. Work one phase at a time. Start each phase by listing the files you'll create, then build, then run tests.
2. Follow the folder structure and layering in Architecture: no SQL in routes, no HTTP concerns in services.
3. Use type hints everywhere and Pydantic schemas for every request and response.
4. Store money as `Decimal`, never `float`, in Python and the DB.
5. Write tests alongside code; a phase isn't done until its tests pass.
6. Create anonymized fixture statements yourself for tests; never ask for real statements.
7. Record any decision this doc doesn't cover in `docs/DECISIONS.md` with one line of reasoning.
8. Keep the README updated: setup steps, env vars, how to run tests, features per phase.
9. Ask before adding a dependency not listed in Tech stack.
