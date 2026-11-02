import { ArrowRight, CircleAlert, CircleCheck, PartyPopper, Target, TrendingDown, TrendingUp } from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useGeneratePlan, useMonthReview } from "@/api/queries";
import type { ReviewCategory } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { CategoryDot, EmptyState } from "@/components/common";
import { InsightCard } from "@/components/Insights";
import { MonthSwitcher } from "@/components/PeriodControls";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatINR, formatMonthLong, parseISODate, toNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

const LABEL: Record<ReviewCategory["label"], { text: string; tone: "good" | "critical" | "neutral" | "warning" }> = {
  under: { text: "Under", tone: "good" },
  on_target: { text: "On target", tone: "neutral" },
  over: { text: "Over", tone: "critical" },
  unplanned: { text: "Unplanned", tone: "warning" },
};

function Compare({ label, planned, actual, goodWhen }: { label: string; planned: string; actual: string; goodWhen: "higher" | "lower" }) {
  const p = toNumber(planned);
  const a = toNumber(actual);
  const good = goodWhen === "higher" ? a >= p : a <= p;
  const max = Math.max(p, a, 1);
  return (
    <Card className="p-5">
      <p className="text-[13px] font-medium text-text-2">{label}</p>
      <p className="tabular mt-1.5 text-[26px] font-semibold leading-none tracking-[-0.03em]">{formatINR(actual)}</p>
      <p className={cn("mt-1.5 text-xs", good ? "text-good-ink" : "text-critical-ink")}>
        {a === p ? "Exactly as planned" : `${formatINR(Math.abs(a - p))} ${a > p ? "more" : "less"} than planned`}
      </p>
      <div className="mt-4 grid gap-1.5">
        {[
          { k: "Planned", v: p, c: "var(--series-muted)" },
          { k: "Actual", v: a, c: good ? "var(--good)" : "var(--critical)" },
        ].map((r) => (
          <div key={r.k} className="flex items-center gap-2 text-[11.5px] text-text-3">
            <span className="w-12">{r.k}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full" style={{ width: `${(r.v / max) * 100}%`, background: r.c }} />
            </div>
            <span className="tabular w-20 text-right">{formatINR(r.v)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Highlight({ title, icon: Icon, rows, empty, tone }: { title: string; icon: typeof TrendingUp; rows: ReviewCategory[]; empty: string; tone: "good" | "bad" }) {
  const categories = useCategoryMap();
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2"><Icon className={cn("size-4", tone === "good" ? "text-good" : "text-critical")} />{title}</span>} />
      <ul className="grid gap-1 p-3 pt-3">
        {rows.length === 0 && <li className="px-2 py-4 text-sm text-text-3">{empty}</li>}
        {rows.map((r) => {
          const cat = r.category_id ? categories.get(r.category_id) : null;
          const diff = Math.abs(toNumber(r.diff));
          return (
            <li key={r.category_id ?? "none"} className="flex items-center gap-3 rounded-xl px-2 py-2">
              <CategoryDot category={cat} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{cat?.name ?? "Uncategorized"}</p>
                <p className="tabular text-xs text-text-3">
                  {formatINR(r.actual)} of {toNumber(r.planned) > 0 ? formatINR(r.planned) : "nothing planned"}
                </p>
              </div>
              <span className={cn("tabular text-sm font-semibold", tone === "good" ? "text-good-ink" : "text-critical-ink")}>
                {tone === "good" ? "−" : "+"}
                {formatINR(diff)}
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export default function MonthReviewPage() {
  const { month = "" } = useParams();
  const navigate = useNavigate();
  const valid = /^\d{4}-\d{2}$/.test(month);
  const { data: review, isLoading } = useMonthReview(month);
  const categories = useCategoryMap();
  const nextMonth = review?.next_month ?? "";
  const generateNext = useGeneratePlan(nextMonth);

  if (!valid) return <Navigate to="/dashboard" replace />;
  const monthDate = parseISODate(`${month}-01`);
  const label = formatMonthLong(monthDate);

  return (
    <div className="animate-fade-up">
      <PageHeader
        title={`${label.split(" ")[0]} in review`}
        description="How the month went against the plan."
        actions={
          <>
            <MonthSwitcher month={monthDate} onChange={(d) => navigate(`/review/${monthKey(d)}`)} />
            {review && (
              <Button
                variant="brand"
                loading={generateNext.isPending}
                onClick={() =>
                  generateNext.mutate(undefined, {
                    onSuccess: () => navigate(`/plan/${nextMonth}`),
                    onError: (err) => {
                      // The next plan may already exist (or be active): just open it.
                      if ((err as { response?: { status?: number } }).response?.status === 409) navigate(`/plan/${nextMonth}`);
                      else toast.error(errorMessage(err));
                    },
                  })
                }
              >
                Plan next month <ArrowRight />
              </Button>
            )}
          </>
        }
      />

      {isLoading ? (
        <Skeleton className="h-80 rounded-2xl" />
      ) : !review ? (
        <Card>
          <EmptyState icon={Target} title={`No plan for ${label}`} description="Reviews compare a month against its plan. Plan a month to review it afterwards." action={<Button asChild><Link to={`/plan/${month}`}>Plan {label.split(" ")[0]}</Link></Button>} />
        </Card>
      ) : (
        <div className="grid gap-5">
          <Card className={cn("relative overflow-hidden p-6 sm:p-7", review.savings_hit ? "" : "")}>
            <div className={cn("pointer-events-none absolute -right-20 -top-20 size-72 rounded-full", review.savings_hit ? "bg-[radial-gradient(circle,var(--good-soft),transparent_70%)]" : "bg-[radial-gradient(circle,var(--critical-soft),transparent_70%)]")} aria-hidden />
            <div className="relative flex flex-wrap items-center gap-5">
              <span className={cn("grid size-14 place-items-center rounded-2xl", review.savings_hit ? "bg-good-soft text-good-ink" : "bg-critical-soft text-critical-ink")}>
                {review.savings_hit ? <PartyPopper className="size-7" /> : <CircleAlert className="size-7" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-2">Savings goal</p>
                <p className="mt-0.5 text-2xl font-semibold tracking-tight sm:text-[28px]">
                  {review.savings_hit
                    ? `Hit — ${formatINR(review.savings_diff)} above target`
                    : `Missed by ${formatINR(-toNumber(review.savings_diff))}`}
                </p>
                <p className="mt-1 text-sm text-text-2">
                  You kept {formatINR(review.savings.actual)} against a target of {formatINR(review.savings.planned)}.
                </p>
              </div>
              <Badge tone={review.status === "closed" ? "neutral" : "brand"} className="px-2.5 py-1 text-xs">
                {review.status === "closed" ? "Month closed" : "Month in progress"}
              </Badge>
            </div>
          </Card>

          <div className="grid gap-4 md:grid-cols-3">
            <Compare label="Income" planned={review.income.planned} actual={review.income.actual} goodWhen="higher" />
            <Compare label="Spending" planned={review.spending.planned} actual={review.spending.actual} goodWhen="lower" />
            <Compare label="Saved" planned={review.savings.planned} actual={review.savings.actual} goodWhen="higher" />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Highlight title="Biggest overspends" icon={TrendingUp} rows={review.overspends} empty="Nothing went over plan. Impressive." tone="bad" />
            <Highlight title="Biggest wins" icon={TrendingDown} rows={review.wins} empty="No category came in under plan this time." tone="good" />
          </div>

          {review.insights.length > 0 && (
            <Card>
              <CardHeader title="What stood out" />
              <div className="grid gap-3 p-5 md:grid-cols-3">
                {review.insights.map((i) => (
                  <InsightCard key={`${i.kind}-${i.category_id}-${i.title}`} insight={i} />
                ))}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader title="Every category" description="Planned vs actual" />
            <div className="overflow-x-auto p-2 pt-3">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-3">
                    <th className="px-3 pb-2 font-medium">Category</th>
                    <th className="px-3 pb-2 text-right font-medium">Planned</th>
                    <th className="px-3 pb-2 text-right font-medium">Actual</th>
                    <th className="px-3 pb-2 text-right font-medium">Difference</th>
                    <th className="px-3 pb-2 text-right font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {review.categories.map((c) => {
                    const cat = c.category_id ? categories.get(c.category_id) : null;
                    const diff = toNumber(c.diff);
                    return (
                      <tr key={c.category_id ?? "none"} className="border-t border-border">
                        <td className="px-3 py-2.5">
                          <span className="flex items-center gap-2.5">
                            <CategoryDot category={cat} size="sm" />
                            <span className="font-medium">{cat?.name ?? "Uncategorized"}</span>
                          </span>
                        </td>
                        <td className="tabular px-3 py-2.5 text-right text-text-2">{formatINR(c.planned)}</td>
                        <td className="tabular px-3 py-2.5 text-right font-medium">{formatINR(c.actual)}</td>
                        <td className={cn("tabular px-3 py-2.5 text-right", diff < 0 ? "text-critical-ink" : diff > 0 ? "text-good-ink" : "text-text-3")}>
                          {diff === 0 ? "—" : `${diff < 0 ? "+" : "−"}${formatINR(Math.abs(diff))}`}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <Badge tone={LABEL[c.label].tone}>
                            {c.label === "on_target" && <CircleCheck />}
                            {LABEL[c.label].text}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
