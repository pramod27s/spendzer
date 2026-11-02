import { Banknote, ChartPie, PiggyBank, Target, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAccounts, useCategoryBreakdown, useDaily, useMerchants, useSummary, useTrend } from "@/api/queries";
import type { PeriodQuery } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { BucketSplit, CategoryDonut, DailyBars, TrendBars, useDonutData, WeekdayBars } from "@/components/charts/Charts";
import { CategoryDot, EmptyState, KpiCard, MerchantAvatar, UploadCta } from "@/components/common";
import { InsightsPanel } from "@/components/Insights";
import { PeriodPicker } from "@/components/PeriodControls";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatINR, formatMonthLong, formatPct, parseISODate, pctChange, toNumber } from "@/lib/format";

export default function AnalyticsPage() {
  const navigate = useNavigate();
  const categories = useCategoryMap();
  const { data: accounts = [] } = useAccounts();
  const [q, setQ] = useState<PeriodQuery>({ period: "last_3" });

  const summary = useSummary(q);
  const breakdown = useCategoryBreakdown(q);
  const merchants = useMerchants(q, 10);
  const daily = useDaily(q);
  const endMonth = summary.data?.period.end;
  const trend = useTrend(12, endMonth, q.account_id, !!endMonth);
  const donut = useDonutData(breakdown.data?.categories);

  const s = summary.data;
  const rate = s?.savings_rate != null ? toNumber(s.savings_rate) : null;
  const total = toNumber(breakdown.data?.total);
  const maxCat = useMemo(() => Math.max(...(breakdown.data?.categories ?? []).map((c) => toNumber(c.amount)), 1), [breakdown.data]);
  const empty = s && !s.has_data;

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Analytics"
        description={s ? s.period.label : "How your income and spending divide up."}
        actions={
          <>
            <PeriodPicker value={q} onChange={setQ} />
            <Select
              size="sm"
              value={q.account_id ?? "all"}
              onValueChange={(v) => setQ({ ...q, account_id: v === "all" ? undefined : v })}
              options={[{ value: "all", label: "All accounts" }, ...accounts.map((a) => ({ value: a.id, label: a.name }))]}
              className="h-[34px] w-40"
              aria-label="Account"
            />
          </>
        }
      />

      <div className="grid gap-4 lg:gap-5">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-5">
          <KpiCard label="Total income" icon={Banknote} loading={summary.isLoading} value={formatINR(s?.income)} delta={s && pctChange(s.income, s.previous.income)} footnote="vs previous period" />
          <KpiCard label="Total spending" icon={Wallet} loading={summary.isLoading} value={formatINR(s?.spending)} delta={s && pctChange(s.spending, s.previous.spending)} deltaGoodWhen="down" footnote="vs previous period" />
          <KpiCard label="Net savings" icon={PiggyBank} loading={summary.isLoading} value={formatINR(s?.net_savings)} tone={s && toNumber(s.net_savings) < 0 ? "critical" : undefined} />
          <KpiCard
            label="Savings rate"
            icon={Target}
            loading={summary.isLoading}
            value={rate === null ? "—" : formatPct(rate)}
            tone={rate !== null && rate < 10 ? "critical" : undefined}
            footnote={rate !== null && rate < 10 ? "Below 10%" : undefined}
          />
        </div>

        {empty ? (
          <Card>
            <EmptyState icon={ChartPie} title="Nothing to analyse in this period" description="Pick a longer period, or upload a statement that covers it." action={<UploadCta />} />
          </Card>
        ) : (
          <>
            <Card>
              <CardHeader title="Category split" description={`${breakdown.data?.categories.length ?? 0} categories · click one to see its transactions`} />
              <div className="grid gap-6 p-5 lg:grid-cols-[260px_1fr] lg:gap-10">
                {breakdown.isLoading ? (
                  <Skeleton className="mx-auto size-[240px] rounded-full" />
                ) : (
                  <CategoryDonut data={donut} total={total} size={240} />
                )}
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[420px] text-sm">
                    <thead>
                      <tr className="text-left text-xs text-text-3">
                        <th className="pb-2 font-medium">Category</th>
                        <th className="w-[40%] pb-2 font-medium">Share</th>
                        <th className="pb-2 text-right font-medium">Spent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {breakdown.data?.categories.map((c) => (
                        <tr
                          key={c.category_id ?? c.name}
                          className="cursor-pointer border-t border-border transition-colors hover:bg-surface-2/50"
                          onClick={() =>
                            c.category_id &&
                            navigate(`/transactions?category_id=${c.category_id}&start=${breakdown.data!.period.start}&end=${breakdown.data!.period.end}`)
                          }
                        >
                          <td className="py-2.5 pr-3">
                            <span className="flex items-center gap-2.5">
                              <CategoryDot category={c} size="sm" />
                              <span className="truncate font-medium">{c.name}</span>
                              <span className="text-xs text-text-3">{c.count}×</span>
                            </span>
                          </td>
                          <td className="py-2.5 pr-3">
                            <div className="flex items-center gap-2">
                              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                                <div className="h-full rounded-full bg-[var(--series-1)]" style={{ width: `${(toNumber(c.amount) / maxCat) * 100}%` }} />
                              </div>
                              <span className="tabular w-11 text-right text-xs text-text-3">{formatPct(c.pct)}</span>
                            </div>
                          </td>
                          <td className="tabular py-2.5 text-right font-medium">{formatINR(c.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </Card>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] lg:items-start lg:gap-5">
              <Card>
                <CardHeader title="Fixed, variable, discretionary" description="How much of your money is already spoken for" />
                <div className="p-5">{breakdown.data ? <BucketSplit buckets={breakdown.data.buckets} /> : <Skeleton className="h-24" />}</div>
              </Card>
              <Card>
                <CardHeader title="Monthly trend" description="Income and spending over the last 12 months" />
                <div className="p-5 pt-4">
                  {trend.data ? <TrendBars points={trend.data.points} height={240} /> : <Skeleton className="h-[240px]" />}
                </div>
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:gap-5">
              <Card>
                <CardHeader title="Daily spending" description="Spending per day in this period" />
                <div className="p-5 pt-4">{daily.data ? <DailyBars days={daily.data.days} /> : <Skeleton className="h-[200px]" />}</div>
              </Card>
              <Card>
                <CardHeader title="Day-of-week pattern" description="Average spent per weekday · busiest day highlighted" />
                <div className="p-5 pt-4">{daily.data ? <WeekdayBars weekdays={daily.data.weekdays} /> : <Skeleton className="h-[200px]" />}</div>
              </Card>
            </div>

            {endMonth && (
              <InsightsPanel month={endMonth.slice(0, 7)} title={`Insights for ${formatMonthLong(parseISODate(endMonth)).split(" ")[0]}`} />
            )}

            <Card>
              <CardHeader title="Top merchants" description="Ranked by total spent" />
              <div className="overflow-x-auto p-2 pt-3">
                <table className="w-full min-w-[480px] text-sm">
                  <thead>
                    <tr className="text-left text-xs text-text-3">
                      <th className="w-10 px-3 pb-2 font-medium">#</th>
                      <th className="px-3 pb-2 font-medium">Merchant</th>
                      <th className="px-3 pb-2 text-right font-medium">Payments</th>
                      <th className="px-3 pb-2 text-right font-medium">Average</th>
                      <th className="px-3 pb-2 text-right font-medium">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {merchants.data?.merchants.map((m, i) => {
                      const cat = m.category_id ? categories.get(m.category_id) : null;
                      return (
                        <tr
                          key={m.merchant}
                          className="cursor-pointer border-t border-border transition-colors hover:bg-surface-2/50"
                          onClick={() => navigate(`/transactions?merchant=${encodeURIComponent(m.merchant)}`)}
                        >
                          <td className="tabular px-3 py-2.5 text-text-3">{i + 1}</td>
                          <td className="px-3 py-2.5">
                            <span className="flex items-center gap-3">
                              <MerchantAvatar name={m.merchant} category={cat} />
                              <span className="min-w-0">
                                <span className="block truncate font-medium">{m.merchant}</span>
                                <span className="block truncate text-xs text-text-3">{cat?.name ?? "Uncategorized"}</span>
                              </span>
                            </span>
                          </td>
                          <td className="tabular px-3 py-2.5 text-right text-text-2">{m.count}</td>
                          <td className="tabular px-3 py-2.5 text-right text-text-2">{formatINR(toNumber(m.amount) / m.count)}</td>
                          <td className="tabular px-3 py-2.5 text-right font-medium">{formatINR(m.amount)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
