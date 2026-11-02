import { ArrowRight, CircleAlert, CircleCheck, ClipboardCheck, Gauge, Target, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { useTracking } from "@/api/queries";
import type { TrackingRow } from "@/api/types";
import { CategoryDot } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatINR, toNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS = {
  on_track: { bar: "var(--good)", icon: CircleCheck, text: "text-good-ink", label: "On track" },
  warning: { bar: "var(--warning)", icon: TriangleAlert, text: "text-warning-ink", label: "Close to limit" },
  over: { bar: "var(--critical)", icon: CircleAlert, text: "text-critical-ink", label: "Over" },
} as const;

export function BudgetProgress({ row, name, category }: { row: TrackingRow; name: string; category?: Parameters<typeof CategoryDot>[0]["category"] }) {
  const meta = STATUS[row.status];
  const planned = toNumber(row.planned);
  const spent = toNumber(row.spent);
  const pct = planned > 0 ? Math.min(100, (spent / planned) * 100) : spent > 0 ? 100 : 0;
  const remaining = toNumber(row.remaining);
  return (
    <div className="flex items-center gap-3">
      <CategoryDot category={category} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-[13.5px] font-medium">{name}</p>
          <p className="tabular text-[13px]">
            <span className="font-medium">{formatINR(spent)}</span>
            <span className="text-text-3"> / {planned > 0 ? formatINR(planned) : "unplanned"}</span>
          </p>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
          <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${pct}%`, background: meta.bar }} />
        </div>
        <p className={cn("mt-1 flex items-center gap-1 text-[11.5px]", meta.text)}>
          <meta.icon className="size-3" />
          {meta.label}
          <span className="text-text-3">
            {" · "}
            {remaining >= 0 ? `${formatINR(remaining)} left` : `${formatINR(-remaining)} over`}
            {row.pct_used !== null && ` · ${Math.round(toNumber(row.pct_used))}%`}
          </span>
        </p>
        {row.pace_warning && row.projected && (
          <p className="mt-0.5 flex items-center gap-1 text-[11.5px] text-warning-ink">
            <Gauge className="size-3" /> On pace for {formatINR(row.projected)} by month end
          </p>
        )}
      </div>
    </div>
  );
}

/** Dashboard card: plan vs actual for a month, or a nudge to plan it. */
export function PlanProgressCard({ month, isCurrentMonth }: { month: string; isCurrentMonth: boolean }) {
  const { data, isLoading } = useTracking(month);
  const categories = useCategoryMap();

  if (isLoading) return <Skeleton className="h-48 rounded-2xl" />;

  if (!data) {
    if (!isCurrentMonth) return null;
    return (
      <Card className="flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:p-6">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-ink">
          <Target className="size-5" />
        </span>
        <div className="flex-1">
          <p className="font-semibold">No plan for this month yet</p>
          <p className="text-sm text-text-2">Take savings off the top and give every other rupee a job. It takes a minute.</p>
        </div>
        <Button asChild variant="brand">
          <Link to={`/plan/${month}`}>
            Plan this month <ArrowRight />
          </Link>
        </Button>
      </Card>
    );
  }

  const planned = toNumber(data.planned_total);
  const spent = toNumber(data.spent_total);
  const rows = data.rows.filter((r) => toNumber(r.planned) > 0 || toNumber(r.spent) > 0).slice(0, 8);
  const overall = planned > 0 ? Math.min(100, (spent / planned) * 100) : 0;
  const timePct = (data.days_elapsed / data.days_in_month) * 100;

  return (
    <Card>
      <CardHeader
        title="Plan vs actual"
        description={
          data.status === "draft"
            ? "Draft plan — activate it to start tracking"
            : data.days_left === 0
              ? "This month is over — see how it went"
              : `Day ${data.days_elapsed} of ${data.days_in_month}`
        }
        action={
          data.days_left === 0 ? (
            <Button asChild variant="secondary" size="sm">
              <Link to={`/review/${month}`}>
                <ClipboardCheck /> Month-end review
              </Link>
            </Button>
          ) : (
            <Button asChild variant="ghost" size="sm">
              <Link to={`/plan/${month}`}>
                Open plan <ArrowRight />
              </Link>
            </Button>
          )
        }
      />
      <div className="grid gap-6 p-5 lg:grid-cols-[260px_1fr]">
        <div>
          <p className="tabular text-[28px] font-semibold leading-none tracking-[-0.03em]">{formatINR(spent)}</p>
          <p className="mt-1 text-sm text-text-3">of {formatINR(planned)} planned</p>
          <div className="relative mt-4 h-2 overflow-visible rounded-full bg-surface-2">
            <div
              className="h-full rounded-full"
              style={{ width: `${overall}%`, background: spent > planned ? "var(--critical)" : "var(--brand)" }}
            />
            <div className="absolute -top-1 h-4 w-0.5 rounded bg-text-3" style={{ left: `${timePct}%` }} aria-hidden />
          </div>
          <p className="mt-2 text-xs text-text-3">The tick marks how far through the month you are.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((r) => {
            const cat = r.category_id ? categories.get(r.category_id) : null;
            return <BudgetProgress key={r.category_id ?? "none"} row={r} name={cat?.name ?? "Uncategorized"} category={cat} />;
          })}
        </div>
      </div>
    </Card>
  );
}


/** The single most useful number mid-month: what you can spend today and stay on plan. */
export function SafeToSpendCard({ month }: { month: string }) {
  const { data } = useTracking(month);
  if (!data || data.status !== "active" || data.safe_to_spend == null) return null;
  const left = Math.max(0, toNumber(data.flexible_planned) - toNumber(data.flexible_spent));
  const used = toNumber(data.flexible_planned) > 0 ? Math.min(100, (toNumber(data.flexible_spent) / toNumber(data.flexible_planned)) * 100) : 0;
  const zero = toNumber(data.safe_to_spend) === 0;
  return (
    <Card className="relative overflow-hidden p-6 sm:p-7">
      <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-[radial-gradient(circle,var(--brand-soft),transparent_70%)]" aria-hidden />
      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-text-2">Safe to spend today</p>
          <p className={cn("tabular mt-1 text-[52px] font-semibold leading-none tracking-[-0.04em] sm:text-[60px]", zero && "text-critical-ink")}>
            {formatINR(data.safe_to_spend)}
          </p>
          <p className="mt-3 text-sm text-text-2">
            {zero
              ? "Your everyday and lifestyle budget is used up. Fixed costs are still covered."
              : `${formatINR(left)} left for everyday and lifestyle spending · ${data.days_left} ${data.days_left === 1 ? "day" : "days"} to go, today included`}
          </p>
        </div>
        <div className="w-full sm:w-64">
          <div className="flex justify-between text-xs text-text-3">
            <span>Flexible budget used</span>
            <span className="tabular">{Math.round(used)}%</span>
          </div>
          <div className="relative mt-1.5 h-2 rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-brand transition-[width] duration-500" style={{ width: `${used}%` }} />
            <div
              className="absolute -top-1 h-4 w-0.5 rounded bg-text-3"
              style={{ left: `${(data.days_elapsed / data.days_in_month) * 100}%` }}
              aria-hidden
            />
          </div>
          <p className="mt-1.5 text-[11.5px] text-text-3">Tick = how far through the month you are</p>
        </div>
      </div>
    </Card>
  );
}
