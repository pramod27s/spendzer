# Decisions

Choices the build spec didn't make, one line of reasoning each. Newest at the bottom of each phase.

## Phase 1

- **Docker Postgres on host port 5433**, not 5432 — the dev machine already runs a local Postgres on 5432; 5433 avoids a clash without touching it.
- **Implied dependencies added** — `asyncpg` (async Postgres driver), `uvicorn` (ASGI server), `python-multipart` (FastAPI file uploads), `pyyaml` (the spec's `seed/*.yaml`), `pytest-cov` (the 80% coverage target), and the shadcn/ui building blocks (`@radix-ui/*`, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `sonner`) plus `react-router-dom` for the routes. Each is required by a listed choice rather than a new capability.
- **`bcrypt` pinned to 4.0.1** — `passlib` 1.7 breaks on newer bcrypt releases.
- **Full schema created in the first migration** (plans, alerts, recurring groups too) — the spec defines it up front and `transactions.recurring_group_id` needs its target table anyway.
- **Enums are VARCHAR + CHECK constraints**, not native Postgres enums — far easier to add values in later migrations.
- **`refresh_tokens` table** (not in the spec) — rotation needs server state; each refresh token is a JWT whose `jti` is stored, revoked on use, and replaying a revoked token ends every session for that user.
- **Access token in the response body, refresh token only in the httpOnly cookie**, path-scoped to `/api/v1/auth` — the browser never exposes the refresh token to JS.
- **Same-origin API** — Vite proxies `/api` in dev; in production Vercel should rewrite `/api/*` to the API host. SameSite=Strict cookies don't cross sites, so the frontend and API must look like one site.
- **`COOKIE_SECURE` setting** — true by default; set false only for plain-http local dev.
- **Money crosses the API as strings** ("1234.50") — JSON numbers are floats; strings keep `Decimal` precision end to end.
- **Upload status `needs_mapping`** added to the spec's list — a generic CSV with no saved mapping waits for the user instead of failing.
- **Files awaiting a column mapping are parked in a private temp dir** (mode 0600) and deleted after parsing, on upload deletion, or after 60 minutes — the only time raw bytes touch disk; everything else is parsed in memory.
- **Column mapping stored on the account** (`accounts.column_mapping` JSONB) — the spec says "saved per account"; the header row is re-detected on every file so junk rows above it don't matter.
- **Upload preview (headers + 5 sample rows) is stored on the upload** while it waits for mapping, then cleared once parsing finishes.
- **Card-number masking uses 13–19 digit runs that pass the Luhn check** — the spec says 12–19, but 12-digit runs are almost always UPI reference numbers, which phase-4 dedup needs.
- **Contains-rules match whole words** — otherwise the seeded keyword `vi` (Vodafone Idea) would match "ser*vi*ce".
- **Rule priority: lower number wins; on ties the longer keyword wins** — so "instamart" (Groceries) beats "swiggy" (Food & Dining). User exact rules are created at priority 0.
- **Cashback is categorised under the system "Refund" category** (kind `cashback`) — the spec lists no cashback category and neither counts as income.
- **Card bill payments and credits count as self-transfers**, and debits to brokers / mutual funds count as `investment` — matches "the card's individual purchases are the spending, not the bill".
- **A credit filed under a spending category becomes kind `refund`**, and a debit under an income category stays `expense` — the category picker can't produce nonsensical kinds.
- **Manual credits with no category default to `income`**, not `unknown` — someone typing in cash received is telling us it's income.
- **Every new user gets a "Cash" account**; manual entries default to it — `transactions.account_id` stays NOT NULL.
- **Deleting a user category moves its transactions to "Other"** and drops rules pointing at it.
- **Analytics periods `last_3/6/12` include the current month**; the "previous period" is the same length immediately before.
- **`/analytics/daily` added in phase 1** (spec puts daily spending in analytics generally) — cheap, and it makes the dashboard useful on day one.
- **Summary returns `latest_txn_date`** so the dashboard can jump to the newest month with data instead of showing an empty current month.
- **`xlrd` added for legacy `.xls`** (approved). The test fixture `bank_legacy.xls` was written once with a throwaway `uv run --with xlwt`; `xlwt` is not a project dependency.
- **Category colours use the validated 8-slot categorical palette**; the 8 most common spending categories get distinct slots, rarer ones reuse a hue and are re-slotted at render time if two visible slices would collide. Donuts show the top 6 plus "N more".
- **Charts remount when their dataset shape changes** — Recharts mis-places bars when animating between datasets of different lengths.
- **Rate limiter is in-memory** (slowapi default) — fine for one API instance; switch the storage URI to Redis if it scales out.

## Phase 2

- **Pure fit/cut logic lives in `engine/plan_fit.py`**; `services/planner_service.py` orchestrates the spec's algorithm around it — same layering as the other engines, and unit-testable without a database.
- **Fixed costs are one plan line per category** (summing its recurring groups), not one per group — plan vs actual is per category, so per-group lines would double up. The line's basis names each charge ("Recurring: Netflix ₹649 + Spotify ₹119").
- **Plan lines are unique per (category, source)** — a category can have a fixed line and a forecast line (e.g. a subscription plus one-off purchases), but never two of the same kind.
- **Forecasts cover every spending category, fixed-bucket ones included** (excluding recurring transactions) — otherwise rent that isn't yet detected as recurring would vanish from the plan. Cuts still only touch discretionary and variable lines.
- **"Last 3 months" means the 3 most recent months with data before the plan month** — on 1 Nov the current month is empty, so a literal calendar window would forecast near-zero for everything.
- **Only one outlier month can be ignored** — with three months, two can't both exceed twice the median of the others.
- **Forecasts and fixed amounts are whole rupees** (half-up).
- **Cuts are greedy: largest line first**, each down to its floor before the next — the spec's worked example lists two cuts, but any split meets its rules; greedy keeps suggestions short.
- **Cuts are suggested only on forecast lines**, never on fixed costs or numbers the user typed.
- **`POST /plans/{id}/apply-suggestions` and `POST/DELETE /plans/{id}/items` added** — applying cuts atomically and adding a category to the plan both need an endpoint the spec's list didn't have.
- **Editing a plan line makes it the user's line** (`source = user`) and records the old value in its basis; regeneration skips every category that has a user line.
- **User-entered income and savings survive regeneration** (`income_custom` / `savings_custom` flags); history-derived values are recomputed with the latest data.
- **"Accept shortfall" is a UI acknowledgement only** — nothing changes server-side; activation is allowed with a gap.
- **"Keep as buffer" puts the surplus on the system "Other" category** as a user line.
- **Recurring groups gained `status` (detected / confirmed / dismissed)** — dismissed groups must never be re-created by detection, which needs persistent memory. Detected groups whose pattern breaks are deleted; confirmed ones are kept and only their `active` flag updates.
- **Weekly groups store the weekday (0 = Monday) in `typical_day`**; monthly groups store the day of month. Weekly charges count as ×52/12 per month in plans.
- **Self-transfer pairing only considers debits counted as spending and credits classified `unknown`**, never rows the user set by hand — a salary credit that happens to equal a rent payment shouldn't vanish.
- **Recurring detection and transfer pairing run after every upload**; failures are logged and never fail the upload.
- **`app/core/clock.py` wraps today's date** so tests can pin it — recurring "active" status and tracking depend on it.
- **Plan vs actual shows unplanned spending as "over"** — money spent in a category with no plan line is, by definition, outside the plan.
- **Planner route `/plan` opens the current month before the 20th, next month from the 20th on.**

## Phase 3

- **Plans close lazily**: an active plan whose month has ended is marked `closed` the next time plans, tracking, reviews or alerts are read — no scheduler needed for a single-user app.
- **Closed plans are read-only** (`PLAN_CLOSED`); the review is how you look back.
- **Safe-to-spend counts plan lines by bucket** (variable + discretionary, including one-off events whose category is in those buckets) against spend in the same categories; rounded down to the rupee and floored at 0. It's `null` once the month is over.
- **Pace warnings need an in-progress month**, 7+ days elapsed and a planned amount; a category already over budget gets the `budget_100` alert instead of a pace one.
- **Alerts are de-duplicated on (type, category, month)** — one `budget_80` for Food & Dining in November, ever. Unplanned spending never raises budget alerts (the plan-vs-actual card shows it).
- **Alerts refresh after uploads, manual entries and category changes, and when the alert list is opened** — the last covers time-based rules (`stale_data`, `income_missing`) without a background job.
- **Anomaly baseline is the category's last 90 days and needs 3+ payments**; only the single biggest unusual payment per category alerts.
- **`recurring_change` compares the newest charge from a recurring merchant in the month** to the group's typical amount.
- **`income_missing` watches payers who credited income in at least 2 of the last 3 months**, at their median day of month, with a 5-day grace period; current month only.
- **`stale_data` only fires while a plan is active for the current month** — nothing to keep accurate otherwise.
- **`POST /alerts/read-all` added** for the bell's "Mark all read".
- **Insight cards are templates ranked by rupee impact** (spike / drop / new spend / savings vs target / heavy fixed costs / subscriptions / merchant habit / biggest category), max 5, one card per category. "Biggest category" and "new spend" count half their amount as impact so they don't crowd out actionable cards.
- **Insight history = the 3 most recent earlier months with data**, matching the planner's window.
- **Review queue = expense rows the rules filed under "Other" plus credits classified `unknown`**; answering uses `PATCH /transactions/{id}` with `apply_to_merchant`, so each answer becomes a rule for that merchant / sender.
- **Month-end review labels**: within 5% under plan counts as "on target"; anything with no plan line is "unplanned".
- **"Plan next month" on a review opens the existing plan if one is already active** (the API's 409) instead of erroring.
- **The dashboard stays on the current month when it has a plan**, even before any spending, so safe-to-spend is visible from day 1.

## Phase 4

- **`rapidfuzz` added** (approved) for merchant similarity; `pdfplumber`, `pikepdf`, `scikit-learn` (+ `joblib`) come from the tech stack.
- **PDF fixtures are generated, not hand-made**: `tests/fixtures/make_pdf_fixtures.py` writes them with a throwaway `uv run --with reportlab`. UPI-app PDFs use a TrueType font with the ₹ glyph — Helvetica has none and ₹ would extract as junk.
- **Bank PDF parsers are column aliases over one shared table reader**, with a line-regex fallback for statements without ruled tables. In the fallback, direction comes from the running balance (balance down = money out), then Dr/Cr suffixes, then narration hints.
- **One credit card parser (HDFC)**, as the spec says "start with one issuer". Its line fallback is off: without a balance column direction can't be inferred safely.
- **Bank layouts are best-effort**: built from the published column names, not real statements (we never ask for real ones). When a real export doesn't match, extend that parser's aliases.
- **UPI-app parsers**: Google Pay and PhonePe statement PDFs (line patterns: date, "Paid to / Received from", amount, then a UPI reference line), and Paytm's Excel/CSV export (signed amounts, a UPI Ref No. column). They pass the payee name straight through as the merchant.
- **`transactions.upi_ref`** stores the 12-digit RRN when a source prints one (from a reference column, a UPI narration, or the app's "UPI Transaction ID" / "UTR No." line).
- **PDF passwords travel to the background task in memory** and are dropped right after decrypting; never stored, never logged.
- **A failed upload no longer blocks the same file**: re-uploading replaces the failed attempt. That's how "wrong PDF password → try again" works.
- **Dedup authority: bank and card statements beat UPI-app exports**; the copy gets `dedup_of`. A shared UPI reference decides on its own (equal = duplicate, different = not); without references the spec's rule applies (same direction and amount, ±1 day, token-set similarity ≥ 80). Rows from the same upload are never duplicates of each other.
- **Dedup runs before transfer pairing and recurring detection** in upload post-processing, so neither ever sees a copy.
- **When the kept bank row is uncategorized and the copy isn't, the bank row borrows the copy's category and payee name** — UPI apps usually name the payee better than a bank narration.
- **ML labels are system category names** (one model serves every user); training text is anonymized: digits, VPAs, masked card numbers and transfer jargon are stripped.
- **The model bootstraps from the seed keyword map** (each keyword in a few realistic narration shapes) plus every rule-, override- and user-categorized spend, so a model exists from day one. `C=20`, balanced classes.
- **The model file is a build artifact** (gitignored); `python -m app.ml.train` runs on container start and can be re-run any time. Without a model file the ML layer is simply skipped. Tests switch the layer off unless they train their own model.
- **ML only categorizes debits that no rule matched** and never into income or excluded categories; `categorized_by = "ml"` and `ml_model_version` are stored on the row.
- **Export is CSV of every transaction including duplicates** (marked `counted = duplicate`); text cells starting with `= + - @` are prefixed with `'` to prevent spreadsheet formula injection.
- **Deleting an account asks for the password again** (in the request body) and the UI also asks you to type "delete". Every user-owned table cascades on `users.id`; parked upload files are removed too.

## Phase 5

- **Onboarding is a 3-step wizard** (savings target → first account → first statement) that new registrations land on; every step can be skipped, and the dashboard's empty state links back to it.
- **The account form is shared** between onboarding and the "Add account" dialog; onboarding reuses the real upload dropzone, column mapper and PDF-unlock flow.
- **Demo account** (`demo@spendzer.app` / `spendzer-demo`) is built by `app/seed/demo.py` through the real pipeline (CSV parsing, categorization, recurring detection, Paytm dedup, plans, alerts). Dates are relative to today and the RNG is seeded per day, so it always looks current and is reproducible. Re-running resets it; it can't be deleted through the API (`DEMO_ACCOUNT`).
- **The demo's story is deliberate**: two good months, then an unusual purchase that tips the latest month just under the 20% savings target, so the review, anomaly alert and insights all have something to say.
- **"Try the live demo"** signs in with the public demo credentials (`/login?demo=1`); overridable with `VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD`.
- **Production guards**: `ENVIRONMENT=production` refuses to start with the default or a short `JWT_SECRET`, or with `COOKIE_SECURE=false`.
- **`postgres://` / `postgresql://` URLs are rewritten to `postgresql+asyncpg://`** so a host-provided `DATABASE_URL` works unchanged.
- **Security headers** on every API response (nosniff, `X-Frame-Options: DENY`, referrer policy), `Cache-Control: no-store` on `/api/*`, HSTS in production; Vercel adds the same for the static app.
- **Deploy shape**: Render Blueprint (`render.yaml`: Docker API + Postgres) and Vercel (`frontend/vercel.json`) with a `/api/*` rewrite to Render, so the refresh cookie stays first-party (`SameSite=Strict`) and CORS isn't needed.
- **Container start** (`backend/start.sh`): migrate, seed, train the ML model (failure only disables the ML layer), optionally build the demo (`SEED_DEMO`), then uvicorn on `$PORT` with proxy headers. The image runs as a non-root user and installs from the locked `uv.lock`.
- **`.gitattributes` forces LF for `*.sh`**, so a checkout on Windows can't break the container entrypoint.
- **README screenshots are real captures of the demo account** (light, dark, mobile) taken with headless Chrome.

## After real-data testing (PhonePe CSV)

- **PhonePe is one source (`phonepe`) that accepts PDF, CSV or Excel**; the format is sniffed from the bytes. The CSV layout (preamble, `Date,Time,Transaction Details,Transaction ID,UTR,Transaction Type,…,Amount`, footer disclaimer) was confirmed against a real export, read locally and never stored; the committed fixture is a synthetic copy of the layout.
- **UTRs read from spreadsheets are zero-padded back to 12 digits**, since Excel drops leading zeros from numeric cells.
- **The ML text cleaner strips UPI-app phrasing** ("Paid to", "Received from", …): with character n-grams, "paid" looked like "prepaid"/"postpaid" and sent person-to-person payments to Mobile & Internet.
- **The model learns an abstain label ("Other") from synthetic person names and family words** (amma, akka, maama…); predicting it leaves the payment uncategorized for the review queue. Regularization was relaxed from C=20 to C=5 to curb overconfidence.
- **Local-merchant keywords added**: general stores / provisions / dairy / milk / fruits (Groceries), khaana / biryani / kabab / dosa / darshini / tiffin / canteen (Food), metro / BMRCL / KSRTC "depot manager" (Transport), ekart / delhivery (Shopping), charitable (Donations).
