import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Account,
  AccountType,
  Alert,
  CategoriesBreakdown,
  Category,
  ColumnMapping,
  Daily,
  Insight,
  MonthReview,
  MerchantRow,
  MerchantRule,
  Page,
  PeriodQuery,
  Plan,
  PlanSummary,
  RecurringGroup,
  RecurringStatus,
  ReviewQueue,
  Source,
  Summary,
  Transaction,
  Tracking,
  TransactionFilters,
  TrendPoint,
  TxnKind,
  Upload,
  User,
} from "./types";

const clean = <T extends object>(params: T) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""));

export const keys = {
  me: ["me"] as const,
  accounts: ["accounts"] as const,
  categories: ["categories"] as const,
  rules: ["merchant-rules"] as const,
  sources: ["sources"] as const,
  uploads: ["uploads"] as const,
  upload: (id: string) => ["uploads", id] as const,
  transactions: (f: TransactionFilters) => ["transactions", f] as const,
  analytics: ["analytics"] as const,
};

/* ---------- reads ---------- */

export const useAccounts = () =>
  useQuery({ queryKey: keys.accounts, queryFn: async () => (await api.get<Account[]>("/accounts")).data });

export const useCategories = () =>
  useQuery({
    queryKey: keys.categories,
    queryFn: async () => (await api.get<Category[]>("/categories")).data,
    staleTime: 5 * 60_000,
  });

export const useMerchantRules = () =>
  useQuery({ queryKey: keys.rules, queryFn: async () => (await api.get<MerchantRule[]>("/merchant-rules")).data });

export const useSources = () =>
  useQuery({
    queryKey: keys.sources,
    queryFn: async () => (await api.get<Source[]>("/uploads/sources")).data,
    staleTime: Infinity,
  });

export const useUploads = () =>
  useQuery({
    queryKey: keys.uploads,
    queryFn: async () => (await api.get<Page<Upload>>("/uploads", { params: { size: 50 } })).data,
  });

/** Polls while the upload is being processed. */
export const useUpload = (id: string | null) =>
  useQuery({
    queryKey: keys.upload(id ?? ""),
    enabled: !!id,
    queryFn: async () => (await api.get<Upload>(`/uploads/${id}`)).data,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "pending" || s === "parsing" ? 800 : false;
    },
  });

export const useTransactions = (filters: TransactionFilters) =>
  useQuery({
    queryKey: keys.transactions(filters),
    queryFn: async () =>
      (await api.get<Page<Transaction>>("/transactions", { params: clean(filters) })).data,
    placeholderData: keepPreviousData,
  });

const analyticsQuery = <T,>(path: string, params: object, enabled = true) => ({
  queryKey: [...keys.analytics, path, params],
  queryFn: async () => (await api.get<T>(`/analytics/${path}`, { params: clean(params) })).data,
  placeholderData: keepPreviousData,
  enabled,
});

export const useSummary = (q: PeriodQuery, enabled = true) =>
  useQuery(analyticsQuery<Summary>("summary", q, enabled));

export const useCategoryBreakdown = (q: PeriodQuery, enabled = true) =>
  useQuery(analyticsQuery<CategoriesBreakdown>("categories", q, enabled));

export const useTrend = (months: number, endMonth?: string, accountId?: string, enabled = true) =>
  useQuery(
    analyticsQuery<{ points: TrendPoint[] }>(
      "trend",
      { months, end_month: endMonth, account_id: accountId },
      enabled,
    ),
  );

export const useMerchants = (q: PeriodQuery, limit = 10, enabled = true) =>
  useQuery(analyticsQuery<{ merchants: MerchantRow[] }>("merchants", { ...q, limit }, enabled));

export const useDaily = (q: PeriodQuery, enabled = true) =>
  useQuery(analyticsQuery<Daily>("daily", q, enabled));

/* ---------- writes ---------- */

function useInvalidate() {
  const qc = useQueryClient();
  return (...groups: readonly (readonly string[])[]) =>
    Promise.all(groups.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

/** Anything that changes transactions invalidates lists and analytics. */
// Plans (tracking) and alerts depend on transactions too.
const DATA = [["transactions"], keys.analytics, ["plans"], ["alerts"]] as const;

export function useCreateAccount() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: { name: string; type: AccountType; institution?: string; last4?: string }) =>
      (await api.post<Account>("/accounts", body)).data,
    onSuccess: () => invalidate(keys.accounts),
  });
}

export function useUpdateAccount() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; name?: string; institution?: string; last4?: string }) =>
      (await api.patch<Account>(`/accounts/${id}`, body)).data,
    onSuccess: () => invalidate(keys.accounts),
  });
}

export function useDeleteAccount() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/accounts/${id}`),
    onSuccess: () => invalidate(keys.accounts, keys.uploads, ...DATA),
  });
}

export function useCreateUpload() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: { file: File; account_id: string; source_type: string; pdf_password?: string }) => {
      const form = new FormData();
      form.append("file", body.file);
      form.append("account_id", body.account_id);
      form.append("source_type", body.source_type);
      if (body.pdf_password) form.append("pdf_password", body.pdf_password);
      return (await api.post<Upload>("/uploads", form)).data;
    },
    onSuccess: () => invalidate(keys.uploads),
  });
}

export function useSubmitMapping() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, mapping }: { id: string; mapping: ColumnMapping }) =>
      (await api.post<Upload>(`/uploads/${id}/column-mapping`, mapping)).data,
    onSuccess: (u) => invalidate(keys.uploads, keys.upload(u.id), keys.accounts),
  });
}

export function useDeleteUpload() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/uploads/${id}`),
    onSuccess: () => invalidate(keys.uploads, ...DATA),
  });
}

export function useCreateTransaction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: {
      txn_date: string;
      amount: string;
      direction: "debit" | "credit";
      merchant: string;
      category_id?: string;
      account_id?: string;
      note?: string;
    }) => (await api.post<Transaction>("/transactions", body)).data,
    onSuccess: () => invalidate(...DATA, keys.accounts),
  });
}

export function useUpdateTransaction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: {
      id: string;
      category_id?: string;
      kind?: TxnKind;
      note?: string | null;
      apply_to_merchant?: boolean;
    }) =>
      (await api.patch<{ transaction: Transaction; recategorized: number }>(`/transactions/${id}`, body)).data,
    onSuccess: () => invalidate(...DATA, keys.rules),
  });
}

export function useDeleteTransaction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/transactions/${id}`),
    onSuccess: () => invalidate(...DATA),
  });
}

export function useCreateCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: Pick<Category, "name" | "bucket" | "icon" | "color">) =>
      (await api.post<Category>("/categories", body)).data,
    onSuccess: () => invalidate(keys.categories),
  });
}

export function useDeleteCategory() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/categories/${id}`),
    onSuccess: () => invalidate(keys.categories, keys.rules, ...DATA),
  });
}

export function useDeleteRule() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/merchant-rules/${id}`),
    onSuccess: () => invalidate(keys.rules),
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name?: string; monthly_savings_target_pct?: string }) =>
      (await api.patch<User>("/me", body)).data,
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  });
}

/* ---------- Phase 2: recurring + planner ---------- */

export const planKeys = {
  byMonth: (month: string) => ["plans", "month", month] as const,
  tracking: (month: string) => ["plans", "tracking", month] as const,
  recurring: ["recurring"] as const,
};

export const useRecurring = () =>
  useQuery({
    queryKey: planKeys.recurring,
    queryFn: async () =>
      (await api.get<{ groups: RecurringGroup[]; monthly_total: string }>("/recurring")).data,
  });

export function useUpdateRecurring() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: RecurringStatus }) =>
      (await api.patch<RecurringGroup>(`/recurring/${id}`, { status })).data,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: planKeys.recurring });
      void qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

/** The plan for a month (YYYY-MM), or null when none exists yet. */
export const usePlan = (month: string) =>
  useQuery({
    queryKey: planKeys.byMonth(month),
    queryFn: async () => {
      const list = (await api.get<PlanSummary[]>("/plans", { params: { month } })).data;
      if (!list.length) return null;
      return (await api.get<Plan>(`/plans/${list[0].id}`)).data;
    },
  });

/** Plan vs actual; null when the month has no plan. */
export const useTracking = (month: string, enabled = true) =>
  useQuery({
    queryKey: planKeys.tracking(month),
    enabled,
    queryFn: async () => {
      try {
        return (await api.get<Tracking>("/plans/current/tracking", { params: { month } })).data;
      } catch (err) {
        if ((err as { response?: { status?: number } }).response?.status === 404) return null;
        throw err;
      }
    },
  });

/** Every planner write returns the full plan; drop it straight into the cache. */
function usePlanMutation<V>(month: string, fn: (vars: V) => Promise<Plan>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (plan) => {
      qc.setQueryData(planKeys.byMonth(month), plan);
      void qc.invalidateQueries({ queryKey: planKeys.tracking(month) });
    },
  });
}

export const useGeneratePlan = (month: string) =>
  usePlanMutation(month, async (body: { expected_income?: string; savings_target_pct?: string } | void) =>
    (await api.post<Plan>("/plans/generate", body || null, { params: { month } })).data,
  );

export const useUpdatePlan = (month: string, planId: string) =>
  usePlanMutation(month, async (body: { expected_income?: string; savings_target?: string }) =>
    (await api.patch<Plan>(`/plans/${planId}`, body)).data,
  );

export const useUpdatePlanItem = (month: string, planId: string) =>
  usePlanMutation(month, async ({ itemId, amount }: { itemId: string; amount: string }) =>
    (await api.patch<Plan>(`/plans/${planId}/items/${itemId}`, { planned_amount: amount })).data,
  );

export const useAddPlanItem = (month: string, planId: string) =>
  usePlanMutation(month, async (body: { category_id: string; planned_amount: string }) =>
    (await api.post<Plan>(`/plans/${planId}/items`, body)).data,
  );

export const useDeletePlanItem = (month: string, planId: string) =>
  usePlanMutation(month, async (itemId: string) =>
    (await api.delete<Plan>(`/plans/${planId}/items/${itemId}`)).data,
  );

export const useApplyCuts = (month: string, planId: string) =>
  usePlanMutation(month, async (_: void) => (await api.post<Plan>(`/plans/${planId}/apply-suggestions`)).data);

export const useAddEvent = (month: string, planId: string) =>
  usePlanMutation(
    month,
    async (body: { title: string; amount: string; category_id?: string; expected_date?: string }) =>
      (await api.post<Plan>(`/plans/${planId}/events`, body)).data,
  );

export const useDeleteEvent = (month: string, planId: string) =>
  usePlanMutation(month, async (eventId: string) =>
    (await api.delete<Plan>(`/plans/${planId}/events/${eventId}`)).data,
  );

export const useActivatePlan = (month: string, planId: string) =>
  usePlanMutation(month, async (_: void) => (await api.post<Plan>(`/plans/${planId}/activate`)).data);

/* ---------- Phase 3: alerts, insights, reviews ---------- */

export const p3Keys = {
  alerts: ["alerts"] as const,
  insights: (month: string) => ["analytics", "insights", month] as const,
  review: (month: string) => ["plans", "review", month] as const,
  queue: ["transactions", "review-queue"] as const,
};

export const useAlerts = () =>
  useQuery({
    queryKey: p3Keys.alerts,
    queryFn: async () => (await api.get<{ alerts: Alert[]; unread: number }>("/alerts")).data,
    refetchInterval: 60_000,
  });

export function useMarkAlertRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.patch<Alert>(`/alerts/${id}/read`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: p3Keys.alerts }),
  });
}

export function useMarkAllAlertsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => api.post("/alerts/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: p3Keys.alerts }),
  });
}

export const useInsights = (month: string, enabled = true) =>
  useQuery({
    queryKey: p3Keys.insights(month),
    enabled,
    queryFn: async () =>
      (await api.get<{ month: string; insights: Insight[] }>("/analytics/insights", { params: { month } })).data,
  });

/** Month-end review for a month's plan; null when that month has no plan. */
export const useMonthReview = (month: string) =>
  useQuery({
    queryKey: p3Keys.review(month),
    queryFn: async () => {
      const list = (await api.get<PlanSummary[]>("/plans", { params: { month } })).data;
      if (!list.length) return null;
      return (await api.get<MonthReview>(`/plans/${list[0].id}/review`)).data;
    },
  });

export const useReviewQueue = () =>
  useQuery({
    queryKey: p3Keys.queue,
    queryFn: async () => (await api.get<ReviewQueue>("/transactions/review")).data,
  });

/* ---------- Phase 4: data rights ---------- */

/** Download every transaction as CSV (authenticated, so fetched as a blob). */
export async function downloadTransactionsCsv(): Promise<void> {
  const resp = await api.get<Blob>("/export/transactions.csv", { responseType: "blob" });
  const disposition = String(resp.headers["content-disposition"] ?? "");
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "spendzer-transactions.csv";
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Delete the signed-in user and all their data (asks for the password again). */
export function useDeleteMe() {
  return useMutation({
    mutationFn: async (password: string) => api.delete("/me", { data: { password } }),
  });
}

/** File several transactions under one category (no merchant rules are created). */
export function useBulkCategorize() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: { transaction_ids: string[]; category_id: string }) =>
      (await api.post<{ updated: number }>("/transactions/bulk-categorize", body)).data,
    onSuccess: () => invalidate(...DATA),
  });
}
