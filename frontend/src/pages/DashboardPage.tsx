import { ArrowRight, ArrowUpDown, Banknote, CloudUpload, PiggyBank, Plus, Target, TrendingUp, Wallet, WandSparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useCategoryBreakdown, useDaily, useMerchants, useSummary, useTracking, useTransactions, useTrend } from "@/api/queries";
import type { PeriodQuery } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { CategoryDonut, CategoryTable, DailyBars, TrendBars, useDonutData } from "@/components/charts/Charts";
import { Amount, EmptyState, KpiCard, MerchantAvatar, UploadCta } from "@/components/common";
import { ManualEntryDialog } from "@/components/ManualEntryDialog";
import { MonthSwitcher } from "@/components/PeriodControls";
import { InsightsPanel } from "@/components/Insights";
import { PlanProgressCard, SafeToSpendCard } from "@/components/PlanProgress";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { useAuth } from "@/hooks/useAuth";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatDay, formatINR, formatPct, monthBounds, parseISODate, pctChange, toNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function parseMonthParam(v: string | null): Date | null {
  if (!v || !/^\d{4}-\d{2}$/.test(v)) return null;
  return parseISODate(`${v}-01`);
}

const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

function WelcomeState() {
  return (
    <Card className="overflow-hidden">
      <div className="grid lg:grid-cols-[1.1fr_1fr]">
        <div className="p-7 sm:p-10">
          <p className="text-sm font-medium text-brand-ink">Let's get you set up</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] sm:text-[28px]">
            Upload a statement to see where your money went
          </h2>
          <p className="mt-3 max-w-md text-[15px] leading-relaxed text-text-2">
            Export last month's statement from your bank as CSV or Excel. Spendzer cleans every line, sorts it into
            categories and builds this dashboard for you.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button asChild variant="brand">
              <Link to="/onboarding">
                Set up in 3 steps <ArrowRight />
              </Link>
            </Button>
            <UploadCta label="Just upload a statement" />
          </div>
        </div>
        <ol className="grid gap-px border-t border-border bg-border lg:border-l lg:border-t-0">
          {[
            { icon: CloudUpload, t: "Upload", d: "CSV or Excel from any bank" },
            { icon: WandSparkles, t: "Auto-sort", d: "Merchants and categories detected" },
            { icon: TrendingUp, t: "Understand", d: "Income, spending and savings at a glance" },
          ].map((s, i) => (
            <li key={s.t} className="flex items-center gap-4 bg-surface px-7 py-5">
              <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand-ink">
                <s.icon className="size-5" />
              </span>
              <div>
                <p className="text-sm font-semibold">
                  {i + 1}. {s.t}
                </p>
                <p className="text-[13px] text-text-3">{s.d}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [manualOpen, setManualOpen] = useState(false);
  const categories = useCategoryMap();

  const month = parseMonthParam(params.get("month")) ?? new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  const setMonth = (d: Date) => setParams({ month: monthKey(d) }, { replace: true });
  const bounds = monthBounds(month);
  const q: PeriodQuery = { period: "custom", start: bounds.start, end: bounds.end };

  const summary = useSummary(q);
  const breakdown = useCategoryBreakdown(q);
  const trend = useTrend(6, bounds.start);
  const merchants = useMerchants(q, 5);
  const daily = useDaily(q);
  const recent = useTransactions({ start: bounds.start, end: bounds.end, size: 6 });
  const donut = useDonutData(breakdown.data?.categories);

  // First visit with no data this month: jump to the newest month that has data.
  // ...unless this month has a plan: then safe-to-spend matters even before any spending.
  const thisMonth = useTracking(monthKey(new Date()), !params.get("month"));
  const jumped = useRef(false);
  useEffect(() => {
    const s = summary.data;
    if (jumped.current || !s || params.get("month") || thisMonth.isLoading) return;
    jumped.current = true;
    if (!s.has_data && s.latest_txn_date && !thisMonth.data) setMonth(parseISODate(s.latest_txn_date));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary.data, thisMonth.isLoading]);

  const s = summary.data;
  const loading = summary.isLoading;
  const neverUploaded = s && !s.has_data && !s.latest_txn_date;
  const rate = s?.savings_rate !== null && s?.savings_rate !== undefined ? toNumber(s.savings_rate) : null;
  const firstName = user?.name.split(" ")[0] ?? "";

  const topCategory = useMemo(() => breakdown.data?.categories[0], [breakdown.data]);

  return (
    <div className="animate-fade-up">
      <PageHeader
        title={`${greeting()}, ${firstName}`}
        description={neverUploaded ? "Welcome to Spendzer." : "Here's where your money went."}
        actions={
          !neverUploaded && (
            <>
              <MonthSwitcher month={month} onChange={setMonth} />
              <Button variant="secondary" onClick={() => setManualOpen(true)}>
                <Plus /> Cash entry
              </Button>
              <Button asChild>
                <Link to="/upload">
                  <CloudUpload /> Upload
                </Link>
              </Button>
            </>
          )
        }
      />
      <ManualEntryDialog open={manualOpen} onOpenChange={setManualOpen} />

      {neverUploaded ? (
        <WelcomeState />
      ) : (
        <div className="grid gap-4 lg:gap-5">
          <SafeToSpendCard month={monthKey(month)} />

          {/* KPIs */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-5">
            <KpiCard
              label="Income"
              icon={Banknote}
              loading={loading}
              value={formatINR(s?.income)}
              delta={s?.has_data ? pctChange(s.income, s.previous.income) : null}
              footnote="vs last month"
            />
            <KpiCard
              label="Spent"
              icon={Wallet}
              loading={loading}
              value={formatINR(s?.spending)}
              delta={s?.has_data ? pctChange(s.spending, s.previous.spending) : null}
              deltaGoodWhen="down"
              footnote="vs last month"
            />
            <KpiCard
              label="Saved"
              icon={PiggyBank}
              loading={loading}
              value={formatINR(s?.net_savings)}
              tone={s && toNumber(s.net_savings) < 0 ? "critical" : undefined}
              footnote={s && toNumber(s.net_savings) < 0 ? "Spent more than you earned" : "Income minus spending"}
            />
            <KpiCard
              label="Savings rate"
              icon={Target}
              loading={loading}
              value={rate === null ? "—" : formatPct(rate)}
              tone={rate !== null && rate < 10 ? "critical" : undefined}
              footnote={
                rate === null ? "No income this month" : rate < 10 ? "Below the 10% healthy floor" : `Target ${formatPct(user?.monthly_savings_target_pct ?? 20, 0)}`
              }
            />
          </div>

          <PlanProgressCard month={monthKey(month)} isCurrentMonth={monthKey(month) === monthKey(new Date())} />

          {/* Category split + trend */}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)] lg:gap-5">
            <Card>
              <CardHeader
                title="Where it went"
                description={topCategory ? `${topCategory.name} took ${formatPct(topCategory.pct, 0)} of spending` : "Spending by category"}
                action={
                  <Button asChild variant="ghost" size="sm">
                    <Link to="/analytics">
                      Details <ArrowRight />
                    </Link>
                  </Button>
                }
              />
              <div className="p-5">
                {breakdown.isLoading ? (
                  <Skeleton className="mx-auto size-[200px] rounded-full" />
                ) : donut.length === 0 ? (
                  <EmptyState compact title="No spending this month" description="Upload a statement covering this month." action={<UploadCta />} />
                ) : (
                  <div className="grid items-center gap-5 sm:grid-cols-[200px_1fr] lg:grid-cols-1 xl:grid-cols-[200px_1fr]">
                    <CategoryDonut data={donut} total={toNumber(breakdown.data?.total)} size={200} />
                    <CategoryTable
                      data={donut.slice(0, 5)}
                      onSelect={(key) => navigate(`/transactions?category_id=${key}&start=${bounds.start}&end=${bounds.end}`)}
                    />
                  </div>
                )}
              </div>
            </Card>
            <Card>
              <CardHeader title="Income vs spending" description="Last 6 months" />
              <div className="p-5 pt-4">
                {trend.isLoading ? (
                  <Skeleton className="h-[260px] w-full" />
                ) : trend.data?.points.some((p) => toNumber(p.income) > 0 || toNumber(p.spending) > 0) ? (
                  <TrendBars points={trend.data.points} highlight={monthKey(month)} />
                ) : (
                  <EmptyState compact title="No history yet" description="Upload a few months of statements to see the trend." action={<UploadCta />} />
                )}
              </div>
            </Card>
          </div>

          {/* Daily + merchants */}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:gap-5">
            <Card>
              <CardHeader title="Daily spending" description="Spending on each day of the month" />
              <div className="p-5 pt-4">
                {daily.isLoading ? (
                  <Skeleton className="h-[260px] w-full" />
                ) : daily.data?.days.some((d) => toNumber(d.amount) > 0) ? (
                  <DailyBars days={daily.data.days} height={260} />
                ) : (
                  <EmptyState compact title="Nothing spent yet this month" description="Spending shows up here day by day as statements come in." action={<UploadCta />} />
                )}
              </div>
            </Card>
            <Card>
              <CardHeader title="Top merchants" description="Where you spent the most" />
              <div className="p-3 pt-3">
                {merchants.isLoading ? (
                  <div className="grid gap-2 p-2">
                    {[0, 1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-10" />
                    ))}
                  </div>
                ) : merchants.data?.merchants.length ? (
                  <MerchantList rows={merchants.data.merchants} categories={categories} />
                ) : (
                  <EmptyState compact icon={ArrowUpDown} title="No merchants yet" />
                )}
              </div>
            </Card>
          </div>

          <InsightsPanel month={monthKey(month)} title="What stood out" />

          {/* Recent */}
          <Card>
            <CardHeader
              title="Recent transactions"
              action={
                <Button asChild variant="ghost" size="sm">
                  <Link to={`/transactions?start=${bounds.start}&end=${bounds.end}`}>
                    View all <ArrowRight />
                  </Link>
                </Button>
              }
            />
            <div className="p-2 pt-3">
              {recent.data?.items.length ? (
                <ul>
                  {recent.data.items.map((t) => {
                    const cat = t.category_id ? categories.get(t.category_id) : null;
                    return (
                      <li key={t.id} className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface-2/60">
                        <MerchantAvatar name={t.merchant || "?"} category={cat} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{t.merchant || t.raw_description}</p>
                          <p className="truncate text-xs text-text-3">
                            {cat?.name ?? "Uncategorized"} · {formatDay(t.txn_date)}
                          </p>
                        </div>
                        <Amount value={t.amount} direction={t.direction} className={cn("text-sm", t.kind !== "expense" && t.kind !== "income" && "text-text-3")} />
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <EmptyState compact icon={ArrowUpDown} title="No transactions this month" />
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function MerchantList({
  rows,
  categories,
}: {
  rows: { merchant: string; amount: string; count: number; category_id: string | null }[];
  categories: Map<string, import("@/api/types").Category>;
}) {
  const max = Math.max(...rows.map((r) => toNumber(r.amount)), 1);
  return (
    <ol className="grid gap-1">
      {rows.map((r, i) => {
        const cat = r.category_id ? categories.get(r.category_id) : null;
        return (
          <li key={r.merchant} className="flex items-center gap-3 rounded-xl px-2 py-2">
            <span className="tabular w-4 text-center text-xs text-text-3">{i + 1}</span>
            <MerchantAvatar name={r.merchant} category={cat} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-medium">{r.merchant}</p>
                <p className="tabular text-sm font-medium">{formatINR(r.amount)}</p>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2">
                  <div className="h-full rounded-full bg-[var(--series-1)]" style={{ width: `${(toNumber(r.amount) / max) * 100}%` }} />
                </div>
                <span className="text-[11px] text-text-3">{r.count}×</span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
