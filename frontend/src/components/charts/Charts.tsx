import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";

import type { BucketSlice, CategorySlice, TrendPoint } from "@/api/types";
import { CategoryDot } from "@/components/common";
import { distinctCategoryColors, MUTED_SERIES } from "@/lib/colors";
import {
  formatCompactINR,
  formatDay,
  formatINR,
  formatMonthShort,
  formatPct,
  toNumber,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const AXIS_TICK = { fill: "var(--text-3)", fontSize: 11.5 };

/* ---------- shared tooltip shell ---------- */

function TooltipCard({ title, rows }: { title: string; rows: { label: string; value: string; color?: string; strong?: boolean }[] }) {
  return (
    <div className="min-w-40 rounded-xl border border-border bg-surface px-3 py-2.5 text-xs shadow-[var(--shadow-pop)]">
      <p className="mb-1.5 font-medium text-text">{title}</p>
      <div className="grid gap-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-text-2">
              {r.color && <span className="size-2 rounded-full" style={{ background: r.color }} />}
              {r.label}
            </span>
            <span className={cn("tabular text-text", r.strong && "font-semibold")}>{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-2">
      <span className="size-2.5 rounded-[3px]" style={{ background: color }} />
      {label}
    </span>
  );
}

/* ---------- Category donut + table ---------- */

const DONUT_SLICES = 6;

export interface DonutDatum {
  key: string;
  name: string;
  amount: number;
  pct: number;
  color: string;
  icon: string;
  rawColor: string;
  count: number;
}

export function useDonutData(categories: CategorySlice[] | undefined): DonutDatum[] {
  return useMemo(() => {
    const cats = categories ?? [];
    const top = cats.slice(0, DONUT_SLICES);
    const rest = cats.slice(DONUT_SLICES);
    const colors = distinctCategoryColors(top.map((c) => c.color));
    const data: DonutDatum[] = top.map((c, i) => ({
      key: c.category_id ?? `none-${i}`,
      name: c.name,
      amount: toNumber(c.amount),
      pct: toNumber(c.pct),
      color: colors[i],
      icon: c.icon,
      rawColor: c.color,
      count: c.count,
    }));
    if (rest.length) {
      data.push({
        key: "rest",
        name: `${rest.length} more`,
        amount: rest.reduce((s, c) => s + toNumber(c.amount), 0),
        pct: rest.reduce((s, c) => s + toNumber(c.pct), 0),
        color: MUTED_SERIES,
        icon: "circle-dashed",
        rawColor: "#898781",
        count: rest.reduce((s, c) => s + c.count, 0),
      });
    }
    return data;
  }, [categories]);
}

export function CategoryDonut({ data, total, size = 220 }: { data: DonutDatum[]; total: number; size?: number }) {
  const [active, setActive] = useState<number | null>(null);
  const focus = active !== null ? data[active] : null;
  return (
    <div className="relative mx-auto" style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="amount"
            nameKey="name"
            innerRadius="68%"
            outerRadius="100%"
            paddingAngle={data.length > 1 ? 1.5 : 0}
            cornerRadius={4}
            stroke="var(--surface)"
            strokeWidth={2}
            startAngle={90}
            endAngle={-270}
            isAnimationActive
            animationDuration={600}
            onMouseEnter={(_, i) => setActive(i)}
            onMouseLeave={() => setActive(null)}
          >
            {data.map((d, i) => (
              <Cell
                key={d.key}
                fill={d.color}
                opacity={active === null || active === i ? 1 : 0.35}
                style={{ transition: "opacity 150ms" }}
              />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="text-xs text-text-3">{focus ? focus.name : "Total spent"}</p>
          <p className="tabular mt-0.5 text-[22px] font-semibold tracking-[-0.03em]">
            {formatINR(focus ? focus.amount : total)}
          </p>
          {focus && <p className="text-xs text-text-3">{formatPct(focus.pct)} of spending</p>}
        </div>
      </div>
    </div>
  );
}

export function CategoryTable({ data, onSelect }: { data: DonutDatum[]; onSelect?: (key: string) => void }) {
  return (
    <ul className="grid gap-0.5">
      {data.map((d) => (
        <li key={d.key}>
          <button
            type="button"
            onClick={() => onSelect?.(d.key)}
            disabled={!onSelect || d.key === "rest"}
            className="group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors enabled:hover:bg-surface-2"
          >
            <span className="h-7 w-1 shrink-0 rounded-full" style={{ background: d.color }} aria-hidden />
            <CategoryDot category={{ icon: d.icon, color: d.rawColor }} size="sm" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px] font-medium">{d.name}</span>
              <span className="block text-xs text-text-3">
                {d.count} {d.count === 1 ? "payment" : "payments"}
              </span>
            </span>
            <span className="text-right">
              <span className="tabular block text-[13.5px] font-medium">{formatINR(d.amount)}</span>
              <span className="tabular block text-xs text-text-3">{formatPct(d.pct)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/* ---------- Monthly income vs spending ---------- */

const INCOME_COLOR = "var(--series-3)";
const SPEND_COLOR = "var(--series-1)";

export function TrendBars({ points, height = 260, highlight }: { points: TrendPoint[]; height?: number; highlight?: string }) {
  const data = points.map((p) => ({
    month: p.month,
    income: toNumber(p.income),
    spending: toNumber(p.spending),
    savings: toNumber(p.savings),
  }));
  return (
    <div>
      <div className="mb-3 flex gap-4">
        <LegendItem color={INCOME_COLOR} label="Income" />
        <LegendItem color={SPEND_COLOR} label="Spending" />
      </div>
      {/* Remount when the months change: Recharts mis-places bars when morphing between datasets. */}
      <ResponsiveContainer key={data.map((d) => d.month).join()} width="100%" height={height}>
        <BarChart data={data} barGap={3} barCategoryGap="28%" margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" strokeDasharray="0" />
          <XAxis
            dataKey="month"
            tickFormatter={formatMonthShort}
            tick={(props: { x: number; y: number; payload: { value: string } }) => (
              <text
                x={props.x}
                y={props.y + 12}
                textAnchor="middle"
                fontSize={11.5}
                fill={props.payload.value === highlight ? "var(--text)" : "var(--text-3)"}
                fontWeight={props.payload.value === highlight ? 600 : 400}
              >
                {formatMonthShort(props.payload.value)}
              </text>
            )}
            axisLine={{ stroke: "var(--axis)" }}
            tickLine={false}
          />
          <YAxis tickFormatter={formatCompactINR} tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} />
          <Tooltip
            cursor={{ fill: "var(--surface-2)", radius: 6 }}
            content={({ active, payload, label }: TooltipProps<number, string>) =>
              active && payload?.length ? (
                <TooltipCard
                  title={formatMonthShort(String(label)) + " " + String(label).slice(0, 4)}
                  rows={[
                    { label: "Income", value: formatINR(payload[0]?.payload.income), color: INCOME_COLOR },
                    { label: "Spending", value: formatINR(payload[0]?.payload.spending), color: SPEND_COLOR },
                    { label: "Saved", value: formatINR(payload[0]?.payload.savings), strong: true },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="income" fill={INCOME_COLOR} radius={[4, 4, 0, 0]} maxBarSize={22} animationDuration={500} />
          <Bar dataKey="spending" fill={SPEND_COLOR} radius={[4, 4, 0, 0]} maxBarSize={22} animationDuration={500} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------- Daily spending ---------- */

export function DailyBars({ days, height = 200 }: { days: { date: string; amount: string }[]; height?: number }) {
  const data = days.map((d) => ({ date: d.date, amount: toNumber(d.amount) }));
  const interval = data.length > 45 ? Math.ceil(data.length / 8) : data.length > 14 ? 4 : 0;
  return (
    <ResponsiveContainer key={`${data[0]?.date}-${data.length}`} width="100%" height={height}>
      <BarChart data={data} barCategoryGap="18%" margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis
          dataKey="date"
          tickFormatter={(d: string) => formatDay(d)}
          tick={AXIS_TICK}
          interval={interval}
          axisLine={{ stroke: "var(--axis)" }}
          tickLine={false}
        />
        <YAxis tickFormatter={formatCompactINR} tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)", radius: 4 }}
          content={({ active, payload }: TooltipProps<number, string>) =>
            active && payload?.length ? (
              <TooltipCard
                title={formatDay(payload[0].payload.date, true)}
                rows={[{ label: "Spent", value: formatINR(payload[0].payload.amount), color: SPEND_COLOR, strong: true }]}
              />
            ) : null
          }
        />
        <Bar dataKey="amount" fill={SPEND_COLOR} radius={[3, 3, 0, 0]} maxBarSize={18} animationDuration={500} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ---------- Weekday averages ---------- */

export function WeekdayBars({ weekdays, height = 200 }: { weekdays: { label: string; average: string }[]; height?: number }) {
  const data = weekdays.map((w) => ({ label: w.label, average: toNumber(w.average) }));
  const max = Math.max(...data.map((d) => d.average), 0);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barCategoryGap="30%" margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="label" tick={AXIS_TICK} axisLine={{ stroke: "var(--axis)" }} tickLine={false} />
        <YAxis tickFormatter={formatCompactINR} tick={AXIS_TICK} axisLine={false} tickLine={false} width={56} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)", radius: 6 }}
          content={({ active, payload }: TooltipProps<number, string>) =>
            active && payload?.length ? (
              <TooltipCard
                title={`${payload[0].payload.label} average`}
                rows={[{ label: "Spent per day", value: formatINR(payload[0].payload.average), strong: true }]}
              />
            ) : null
          }
        />
        <Bar dataKey="average" radius={[4, 4, 0, 0]} maxBarSize={36} animationDuration={500}>
          {data.map((d) => (
            <Cell key={d.label} fill={d.average === max && max > 0 ? SPEND_COLOR : "var(--series-muted)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ---------- Bucket split (single stacked bar) ---------- */

const BUCKET_META: Record<BucketSlice["bucket"], { label: string; color: string; hint: string }> = {
  fixed: { label: "Fixed", color: "var(--series-1)", hint: "Rent, EMIs, subscriptions" },
  variable: { label: "Variable", color: "var(--series-2)", hint: "Groceries, transport, bills" },
  discretionary: { label: "Discretionary", color: "var(--series-3)", hint: "Eating out, shopping, fun" },
};

export function BucketSplit({ buckets }: { buckets: BucketSlice[] }) {
  const total = buckets.reduce((s, b) => s + toNumber(b.amount), 0);
  return (
    <div>
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full bg-surface-2" role="img" aria-label="Spending by bucket">
        {total > 0 &&
          buckets
            .filter((b) => toNumber(b.amount) > 0)
            .map((b) => (
              <div
                key={b.bucket}
                className="h-full first:rounded-l-full last:rounded-r-full transition-[width] duration-500"
                style={{ width: `${(toNumber(b.amount) / total) * 100}%`, background: BUCKET_META[b.bucket].color }}
              />
            ))}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {buckets.map((b) => (
          <div key={b.bucket} className="flex gap-2.5">
            <span className="mt-1 size-2.5 shrink-0 rounded-[3px]" style={{ background: BUCKET_META[b.bucket].color }} />
            <div className="min-w-0">
              <p className="text-[13px] font-medium">{BUCKET_META[b.bucket].label}</p>
              <p className="tabular text-[15px] font-semibold">{formatINR(b.amount)}</p>
              <p className="text-xs text-text-3">
                {formatPct(b.pct_of_spending, 0)} of spend
                {b.pct_of_income !== null && ` · ${formatPct(b.pct_of_income, 0)} of income`}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
