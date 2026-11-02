// Mirrors the FastAPI schemas. Money is a decimal string ("1234.50").
export type Money = string;
export type Bucket = "fixed" | "variable" | "discretionary" | "income" | "excluded";
export type Direction = "debit" | "credit";
export type TxnKind =
  | "expense"
  | "income"
  | "refund"
  | "cashback"
  | "self_transfer"
  | "investment"
  | "unknown";
export type CategorizedBy = "rule" | "override" | "ml" | "user";
export type AccountType = "bank" | "upi" | "card" | "cash";
export type UploadStatus = "pending" | "needs_mapping" | "parsing" | "done" | "failed";
export type PeriodName = "this_month" | "last_month" | "last_3" | "last_6" | "last_12" | "custom";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: { field: string; message: string }[] };
}

export interface User {
  id: string;
  email: string;
  name: string;
  monthly_savings_target_pct: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  institution: string | null;
  last4: string | null;
  has_column_mapping: boolean;
  created_at: string;
}

export interface Category {
  id: string;
  name: string;
  bucket: Bucket;
  icon: string;
  color: string;
  is_system: boolean;
}

export interface MerchantRule {
  id: string;
  pattern: string;
  match_type: "contains" | "regex" | "exact";
  category_id: string;
  priority: number;
}

export interface ColumnMapping {
  date_col: string;
  description_col: string;
  amount_mode: "split" | "signed" | "type";
  debit_col?: string | null;
  credit_col?: string | null;
  amount_col?: string | null;
  type_col?: string | null;
}

export interface UploadPreview {
  columns: string[];
  sample_rows: string[][];
  suggested_mapping: Partial<ColumnMapping> & { amount_mode: ColumnMapping["amount_mode"] };
}

export interface Upload {
  id: string;
  account_id: string;
  source_type: string;
  file_name: string;
  status: UploadStatus;
  error: string | null;
  txn_count: number;
  period_start: string | null;
  period_end: string | null;
  preview: UploadPreview | null;
  created_at: string;
}

export interface Source {
  source_type: string;
  label: string;
  group: "bank" | "card" | "upi";
  extensions: string[];
  needs_column_mapping: boolean;
  accepts_password: boolean;
}

export interface Transaction {
  id: string;
  account_id: string;
  upload_id: string | null;
  txn_date: string;
  txn_time: string | null; // "19:23:00" when the source printed a time
  amount: Money;
  direction: Direction;
  raw_description: string;
  merchant: string;
  category_id: string | null;
  kind: TxnKind;
  is_recurring: boolean;
  categorized_by: CategorizedBy;
  note: string | null;
  upi_ref: string | null;
  dedup_of: string | null;
  ml_model_version: string | null;
  created_at: string;
}

export interface TransactionFilters {
  start?: string;
  end?: string;
  category_id?: string;
  account_id?: string;
  kind?: TxnKind;
  direction?: Direction;
  merchant?: string;
  search?: string;
  min_amount?: string;
  max_amount?: string;
  page?: number;
  size?: number;
}

export interface Period {
  name: PeriodName;
  start: string;
  end: string;
  label: string;
}

export interface Totals {
  income: Money;
  spending: Money;
  net_savings: Money;
  savings_rate: string | null;
}

export interface Summary extends Totals {
  period: Period;
  txn_count: number;
  previous: Totals;
  has_data: boolean;
  latest_txn_date: string | null;
}

export interface CategorySlice {
  category_id: string | null;
  name: string;
  icon: string;
  color: string;
  bucket: Bucket;
  amount: Money;
  pct: string;
  count: number;
}

export interface BucketSlice {
  bucket: "fixed" | "variable" | "discretionary";
  amount: Money;
  pct_of_spending: string;
  pct_of_income: string | null;
}

export interface CategoriesBreakdown {
  period: Period;
  total: Money;
  income: Money;
  categories: CategorySlice[];
  buckets: BucketSlice[];
}

export interface TrendPoint {
  month: string;
  income: Money;
  spending: Money;
  savings: Money;
}

export interface MerchantRow {
  merchant: string;
  amount: Money;
  count: number;
  category_id: string | null;
}

export interface Daily {
  period: Period;
  days: { date: string; amount: Money }[];
  weekdays: { weekday: number; label: string; average: Money }[];
}

export interface PeriodQuery {
  period: PeriodName;
  start?: string;
  end?: string;
  account_id?: string;
}

/* ---------- Phase 2: recurring + planner ---------- */

export type Frequency = "monthly" | "weekly" | "yearly";
export type RecurringStatus = "detected" | "confirmed" | "dismissed";
export type PlanStatus = "draft" | "active" | "closed";
export type PlanItemSource = "fixed" | "forecast" | "user";
export type FitStatus = "balanced" | "surplus" | "over_fixable" | "over_unfixable";

export interface RecurringGroup {
  id: string;
  merchant: string;
  category_id: string | null;
  typical_amount: Money;
  monthly_amount: Money;
  typical_day: number;
  frequency: Frequency;
  active: boolean;
  status: RecurringStatus;
  last_date: string | null;
  occurrences: number;
}

export interface PlanItem {
  id: string;
  category_id: string;
  planned_amount: Money;
  bucket: Bucket;
  source: PlanItemSource;
  basis: string;
}

export interface PlannedEvent {
  id: string;
  title: string;
  amount: Money;
  category_id: string | null;
  expected_date: string | null;
}

export interface Cut {
  item_id: string;
  category_id: string;
  current: Money;
  suggested: Money;
  cut: Money;
}

export interface Fit {
  spendable: Money;
  fixed_total: Money;
  variable_total: Money;
  discretionary_total: Money;
  events_total: Money;
  planned_total: Money;
  gap: Money;
  status: FitStatus;
  cuts: Cut[];
  gap_after_cuts: Money;
}

export interface Plan {
  id: string;
  month: string;
  status: PlanStatus;
  expected_income: Money;
  income_basis: string;
  income_custom: boolean;
  savings_target: Money;
  savings_pct: string | null;
  savings_custom: boolean;
  items: PlanItem[];
  events: PlannedEvent[];
  fit: Fit;
}

export interface PlanSummary {
  id: string;
  month: string;
  status: PlanStatus;
  expected_income: Money;
  savings_target: Money;
}

export interface TrackingRow {
  category_id: string | null;
  bucket: Bucket;
  planned: Money;
  spent: Money;
  remaining: Money;
  pct_used: string | null;
  status: "on_track" | "warning" | "over";
  projected: Money | null;
  pace_warning: boolean;
}

export interface Tracking {
  plan_id: string;
  month: string;
  status: PlanStatus;
  expected_income: Money;
  actual_income: Money;
  savings_target: Money;
  planned_total: Money;
  spent_total: Money;
  remaining_total: Money;
  days_in_month: number;
  days_elapsed: number;
  days_left: number;
  flexible_planned: Money;
  flexible_spent: Money;
  safe_to_spend: Money | null;
  rows: TrackingRow[];
}

/* ---------- Phase 3: alerts, insights, reviews ---------- */

export type AlertType =
  | "budget_80"
  | "budget_100"
  | "pace"
  | "anomaly"
  | "recurring_change"
  | "income_missing"
  | "stale_data";

export interface Alert {
  id: string;
  type: AlertType;
  message: string;
  category_id: string | null;
  month: string;
  read: boolean;
  created_at: string;
}

export interface Insight {
  kind: string;
  title: string;
  body: string;
  impact: Money;
  tone: "good" | "bad" | "neutral";
  category_id: string | null;
}

export interface ReviewCategory {
  category_id: string | null;
  bucket: Bucket;
  planned: Money;
  actual: Money;
  diff: Money;
  label: "over" | "under" | "on_target" | "unplanned";
}

export interface MonthReview {
  plan_id: string;
  month: string;
  status: PlanStatus;
  next_month: string;
  income: { planned: Money; actual: Money };
  spending: { planned: Money; actual: Money };
  savings: { planned: Money; actual: Money };
  savings_hit: boolean;
  savings_diff: Money;
  categories: ReviewCategory[];
  overspends: ReviewCategory[];
  wins: ReviewCategory[];
  insights: Insight[];
}

export interface PayeeStats {
  count: number;
  min_amount: Money;
  max_amount: Money;
  median_amount: Money;
  first_date: string;
  last_date: string;
  usual_time: "morning" | "afternoon" | "evening" | "night" | null;
}

export interface ReviewQueue {
  uncategorized: Transaction[];
  unknown_credits: Transaction[];
  total: number;
  payee_stats: Record<string, PayeeStats>;
}
