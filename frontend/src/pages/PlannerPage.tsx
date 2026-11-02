import {
  ArrowRight,
  CalendarPlus,
  Check,
  CircleAlert,
  CircleCheck,
  ClipboardCheck,
  Info,
  PiggyBank,
  Plus,
  RefreshCw,
  Rocket,
  Scissors,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { errorCode, errorMessage } from "@/api/client";
import {
  useActivatePlan,
  useAddEvent,
  useAddPlanItem,
  useApplyCuts,
  useCategories,
  useDeletePlanItem,
  useDeleteEvent,
  useGeneratePlan,
  usePlan,
  useUpdatePlan,
  useUpdatePlanItem,
} from "@/api/queries";
import type { Category, Plan, PlanItem } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { CategoryList, CategoryPicker } from "@/components/CategoryPicker";
import { CategoryDot } from "@/components/common";
import { MoneyInput } from "@/components/ManualEntryDialog";
import { MonthSwitcher } from "@/components/PeriodControls";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger, Tooltip } from "@/components/ui/overlays";
import { Badge, Card, CardHeader, Field, Input, Skeleton } from "@/components/ui/primitives";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatDay, formatINR, formatMonthLong, parseISODate, toISODate, toNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

/** Before the 20th you're planning this month; after it, next month. */
export function defaultPlanMonth(today = new Date()): string {
  return monthKey(today.getDate() >= 20 ? new Date(today.getFullYear(), today.getMonth() + 1, 1) : today);
}

export function PlanIndexRedirect() {
  return <Navigate to={`/plan/${defaultPlanMonth()}`} replace />;
}

/* ---------------- inline amount editor ---------------- */

function AmountEditor({
  value,
  onSave,
  disabled,
  label,
}: {
  value: string;
  onSave: (amount: string) => Promise<unknown>;
  disabled?: boolean;
  label: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  async function commit() {
    if (saving) return;
    const next = draft === "" ? "0" : draft;
    if (toNumber(next) === toNumber(value)) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(next);
      setEditing(false);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          setDraft(String(Math.round(toNumber(value))));
          setEditing(true);
        }}
        className="tabular group/amt inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[15px] font-semibold transition-colors enabled:hover:bg-surface-2 disabled:cursor-default"
        aria-label={`Edit ${label}`}
      >
        {formatINR(value)}
      </button>
    );
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void commit();
      }}
      className="w-32"
    >
      <div
        onKeyDown={(e) => {
          if (e.key === "Escape") setEditing(false);
        }}
        onBlur={() => void commit()}
      >
        <MoneyInput value={draft} onChange={setDraft} />
      </div>
      {saving && <span className="sr-only">Saving</span>}
    </form>
  );
}

/* ---------------- fit check ---------------- */

const SEGMENTS = [
  { key: "fixed_total", label: "Fixed", color: "var(--series-1)" },
  { key: "variable_total", label: "Everyday", color: "var(--series-2)" },
  { key: "discretionary_total", label: "Lifestyle", color: "var(--series-3)" },
  { key: "events_total", label: "One-offs", color: "var(--series-7)" },
] as const;

function FitCheck({ plan, month }: { plan: Plan; month: string }) {
  const fit = plan.fit;
  const categories = useCategoryMap();
  const applyCuts = useApplyCuts(month, plan.id);
  const update = useUpdatePlan(month, plan.id);
  const addItem = useAddPlanItem(month, plan.id);
  const { data: allCats = [] } = useCategories();
  const [acceptedShortfall, setAcceptedShortfall] = useState(false);

  const spendable = toNumber(fit.spendable);
  const planned = toNumber(fit.planned_total);
  const gap = toNumber(fit.gap);
  const scale = Math.max(spendable, planned, 1);
  const editable = plan.status !== "closed";

  const headline =
    fit.status === "surplus"
      ? { icon: CircleCheck, tone: "text-good-ink", text: `${formatINR(-gap)} left unplanned` }
      : fit.status === "balanced"
        ? { icon: CircleCheck, tone: "text-good-ink", text: "Every rupee has a job" }
        : { icon: CircleAlert, tone: "text-critical-ink", text: `${formatINR(gap)} over what you can spend` };

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[13px] font-medium text-text-2">Fit check</p>
          <p className={cn("mt-1 flex items-center gap-2 text-xl font-semibold tracking-tight", headline.tone)}>
            <headline.icon className="size-5" />
            {headline.text}
          </p>
        </div>
        <div className="text-right text-sm">
          <p className="tabular font-medium">
            {formatINR(planned)} <span className="text-text-3">planned of</span> {formatINR(spendable)}
          </p>
          <p className="text-xs text-text-3">spendable after savings</p>
        </div>
      </div>

      {/* Stacked bar against the spendable line */}
      <div className="relative mt-6">
        <div className="flex h-4 w-full gap-[2px] overflow-hidden rounded-full bg-surface-2" role="img" aria-label="Planned spending against what you can spend">
          {SEGMENTS.map((s) => {
            const v = toNumber(fit[s.key]);
            if (v <= 0) return null;
            return <div key={s.key} className="h-full transition-[width] duration-500 first:rounded-l-full" style={{ width: `${(v / scale) * 100}%`, background: s.color }} />;
          })}
        </div>
        <div
          className="absolute -top-1.5 bottom-[-6px] w-0.5 rounded-full bg-text"
          style={{ left: `calc(${(spendable / scale) * 100}% - 1px)` }}
          aria-hidden
        />
        <span
          className="absolute -top-6 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-text-2"
          style={{ left: `${Math.min(92, Math.max(8, (spendable / scale) * 100))}%` }}
        >
          Spendable
        </span>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {SEGMENTS.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5 text-xs text-text-2">
            <span className="size-2.5 rounded-[3px]" style={{ background: s.color }} />
            {s.label}
            <span className="tabular font-medium text-text">{formatINR(fit[s.key])}</span>
          </span>
        ))}
      </div>

      {editable && fit.status === "surplus" && (
        <div className="mt-5 flex flex-col gap-3 rounded-xl bg-good-soft/70 p-4 sm:flex-row sm:items-center">
          <p className="flex-1 text-sm text-text-2">
            You have <span className="font-semibold text-text">{formatINR(-gap)}</span> with no job yet. Give it one:
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              loading={update.isPending}
              onClick={() =>
                update.mutate(
                  { savings_target: String(toNumber(plan.savings_target) - gap) },
                  { onSuccess: () => toast.success("Moved to savings") },
                )
              }
            >
              <PiggyBank /> Move to savings
            </Button>
            <Button
              size="sm"
              variant="secondary"
              loading={addItem.isPending}
              onClick={() => {
                const other = allCats.find((c) => c.name === "Other" && c.is_system);
                if (!other) return;
                const existing = plan.items.find((i) => i.category_id === other.id && i.source === "user");
                addItem.mutate(
                  { category_id: other.id, planned_amount: String(-gap + toNumber(existing?.planned_amount)) },
                  { onSuccess: () => toast.success("Kept as a buffer under Other") },
                );
              }}
            >
              Keep as buffer
            </Button>
          </div>
        </div>
      )}

      {editable && fit.cuts.length > 0 && (
        <div className="mt-5 rounded-xl border border-border p-4">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Scissors className="size-4 text-text-3" /> Suggested cuts
          </p>
          <p className="mt-0.5 text-xs text-text-3">Lifestyle first (never below half), then everyday (never below 80%). Fixed costs are never cut.</p>
          <ul className="mt-3 grid gap-2">
            {fit.cuts.map((c) => {
              const cat = categories.get(c.category_id);
              return (
                <li key={c.item_id} className="flex items-center gap-3 text-sm">
                  <CategoryDot category={cat} size="sm" />
                  <span className="flex-1">
                    Reduce <span className="font-medium">{cat?.name}</span> by{" "}
                    <span className="tabular font-semibold">{formatINR(c.cut)}</span>
                  </span>
                  <span className="tabular text-xs text-text-3">
                    {formatINR(c.current)} → {formatINR(c.suggested)}
                  </span>
                </li>
              );
            })}
          </ul>
          <Button
            size="sm"
            className="mt-4"
            loading={applyCuts.isPending}
            onClick={() =>
              applyCuts.mutate(undefined, {
                onSuccess: () => toast.success("Cuts applied"),
                onError: (err) => toast.error(errorMessage(err)),
              })
            }
          >
            <Check /> Apply suggested cuts
          </Button>
        </div>
      )}

      {editable && fit.status === "over_unfixable" && !acceptedShortfall && (
        <div className="mt-4 rounded-xl border border-critical/30 bg-critical-soft/60 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-critical-ink">
            <CircleAlert className="size-4" /> Even with every cut, you're {formatINR(fit.gap_after_cuts)} short
          </p>
          <p className="mt-1 text-sm text-text-2">Spendzer won't quietly shrink your savings. Your call:</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              loading={update.isPending}
              onClick={() =>
                update.mutate({
                  savings_target: String(Math.max(0, toNumber(plan.savings_target) - toNumber(fit.gap))),
                })
              }
            >
              Lower savings to {formatINR(Math.max(0, toNumber(plan.savings_target) - toNumber(fit.gap)))}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setAcceptedShortfall(true)}>
              Accept the shortfall
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ---------------- income & savings ---------------- */

function IncomeCard({ plan, month }: { plan: Plan; month: string }) {
  const update = useUpdatePlan(month, plan.id);
  const editable = plan.status !== "closed";
  const pct = plan.savings_pct ? toNumber(plan.savings_pct) : 0;
  return (
    <Card className="p-5 sm:p-6">
      <div className="grid gap-5">
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-[13px] font-medium text-text-2">Expected income</p>
            <Tooltip content={plan.income_basis || "Entered by you"}>
              <Info className="size-3.5 text-text-3" />
            </Tooltip>
          </div>
          <AmountEditor
            label="expected income"
            value={plan.expected_income}
            disabled={!editable}
            onSave={(amount) => update.mutateAsync({ expected_income: amount })}
          />
          <p className="px-2 text-xs text-text-3">{plan.income_basis || "Entered by you"}</p>
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-[13px] font-medium text-text-2">Savings, taken out first</p>
            <Tooltip content={plan.savings_custom ? "Set by you for this month" : "Your monthly savings target from Settings"}>
              <Info className="size-3.5 text-text-3" />
            </Tooltip>
          </div>
          <div className="flex items-center gap-2">
            <AmountEditor
              label="savings target"
              value={plan.savings_target}
              disabled={!editable}
              onSave={(amount) => update.mutateAsync({ savings_target: amount })}
            />
            <Badge tone="brand">{pct.toFixed(0)}% of income</Badge>
          </div>
        </div>
        <div className="rounded-xl bg-surface-2/70 px-4 py-3">
          <p className="text-xs text-text-3">Left to spend</p>
          <p className="tabular text-2xl font-semibold tracking-tight">{formatINR(plan.fit.spendable)}</p>
        </div>
      </div>
    </Card>
  );
}

/* ---------------- sections ---------------- */

const SOURCE_BADGE: Record<PlanItem["source"], { label: string; tone: "brand" | "neutral" | "outline" }> = {
  fixed: { label: "Recurring", tone: "brand" },
  forecast: { label: "Forecast", tone: "neutral" },
  user: { label: "Yours", tone: "outline" },
};

function Section({
  title,
  description,
  items,
  plan,
  month,
  allowAdd,
  addBuckets,
}: {
  title: string;
  description: string;
  items: PlanItem[];
  plan: Plan;
  month: string;
  allowAdd?: boolean;
  addBuckets: Category["bucket"][];
}) {
  const categories = useCategoryMap();
  const updateItem = useUpdatePlanItem(month, plan.id);
  const deleteItem = useDeletePlanItem(month, plan.id);
  const addItem = useAddPlanItem(month, plan.id);
  const [open, setOpen] = useState(false);
  const editable = plan.status !== "closed";
  const total = items.reduce((s, i) => s + toNumber(i.planned_amount), 0);
  const used = new Set(plan.items.map((i) => i.category_id));

  return (
    <Card>
      <CardHeader
        title={title}
        description={description}
        action={<span className="tabular text-[15px] font-semibold">{formatINR(total)}</span>}
      />
      <ul className="p-2 pt-3">
        {items.length === 0 && <li className="px-3 py-4 text-sm text-text-3">Nothing here yet.</li>}
        {items.map((item) => {
          const cat = categories.get(item.category_id);
          const badge = SOURCE_BADGE[item.source];
          return (
            <li key={item.id} className="group flex items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-surface-2/50">
              <CategoryDot category={cat} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-medium">{cat?.name ?? "Category"}</p>
                  <Badge tone={badge.tone}>{badge.label}</Badge>
                </div>
                <Tooltip content={item.basis || "—"}>
                  <p className="truncate text-xs text-text-3">{item.basis}</p>
                </Tooltip>
              </div>
              <AmountEditor
                label={cat?.name ?? "amount"}
                value={item.planned_amount}
                disabled={!editable}
                onSave={(amount) => updateItem.mutateAsync({ itemId: item.id, amount })}
              />
              {editable && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                  aria-label={`Remove ${cat?.name}`}
                  onClick={() => deleteItem.mutate(item.id)}
                >
                  <Trash2 />
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      {allowAdd && editable && (
        <div className="border-t border-border p-2">
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button variant="ghost" size="sm" className="text-text-2">
                <Plus /> Add a category
              </Button>
            </PopoverTrigger>
            <PopoverContent className="p-0">
              <CategoryListFiltered
                exclude={used}
                buckets={addBuckets}
                onSelect={(c) => {
                  setOpen(false);
                  addItem.mutate(
                    { category_id: c.id, planned_amount: "0" },
                    { onSuccess: () => toast.success(`${c.name} added — set an amount`) },
                  );
                }}
              />
            </PopoverContent>
          </Popover>
        </div>
      )}
    </Card>
  );
}

function CategoryListFiltered({ exclude, buckets, onSelect }: { exclude: Set<string>; buckets: Category["bucket"][]; onSelect: (c: Category) => void }) {
  // CategoryList shows everything; wrap it so planned / non-spending categories are skipped.
  return (
    <CategoryList
      onSelect={(c) => {
        if (exclude.has(c.id)) {
          toast.info(`${c.name} is already in this plan`);
          return;
        }
        if (!buckets.includes(c.bucket)) {
          toast.info("Only spending categories can be budgeted");
          return;
        }
        onSelect(c);
      }}
    />
  );
}

/* ---------------- one-off events ---------------- */

function EventsCard({ plan, month }: { plan: Plan; month: string }) {
  const categories = useCategoryMap();
  const add = useAddEvent(month, plan.id);
  const remove = useDeleteEvent(month, plan.id);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const editable = plan.status !== "closed";
  const monthStart = plan.month;
  const monthEnd = toISODate(new Date(parseISODate(plan.month).getFullYear(), parseISODate(plan.month).getMonth() + 1, 0));

  return (
    <Card>
      <CardHeader
        title="One-off events"
        description="Fees, trips, gifts — things that won't show up in a forecast"
        action={
          editable && (
            <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
              <CalendarPlus /> Add
            </Button>
          )
        }
      />
      <ul className="p-2 pt-3">
        {plan.events.length === 0 && <li className="px-3 py-4 text-sm text-text-3">No one-offs planned this month.</li>}
        {plan.events.map((e) => {
          const cat = e.category_id ? categories.get(e.category_id) : null;
          return (
            <li key={e.id} className="group flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-surface-2/50">
              <CategoryDot category={cat ?? { icon: "gift", color: "#6250d6" }} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{e.title}</p>
                <p className="text-xs text-text-3">
                  {cat?.name ?? "No category"}
                  {e.expected_date && ` · ${formatDay(e.expected_date)}`}
                </p>
              </div>
              <span className="tabular text-[15px] font-semibold">{formatINR(e.amount)}</span>
              {editable && (
                <Button variant="ghost" size="icon-sm" className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100" aria-label={`Remove ${e.title}`} onClick={() => remove.mutate(e.id)}>
                  <Trash2 />
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title="Add a one-off" description="Planned now, so it doesn't ambush the month.">
          <form
            className="grid gap-4"
            onSubmit={async (ev) => {
              ev.preventDefault();
              if (!title.trim() || !(toNumber(amount) > 0)) return;
              try {
                await add.mutateAsync({
                  title: title.trim(),
                  amount,
                  category_id: categoryId ?? undefined,
                  expected_date: date || undefined,
                });
                setTitle("");
                setAmount("");
                setDate("");
                setCategoryId(null);
                setOpen(false);
              } catch (err) {
                toast.error(errorMessage(err));
              }
            }}
          >
            <Field label="What is it?" htmlFor="ev-title">
              <Input id="ev-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Exam fee, Goa trip" maxLength={160} autoFocus />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Amount" htmlFor="ev-amount">
                <MoneyInput id="ev-amount" value={amount} onChange={setAmount} />
              </Field>
              <Field label="Expected date" htmlFor="ev-date">
                <Input id="ev-date" type="date" value={date} min={monthStart} max={monthEnd} onChange={(e) => setDate(e.target.value)} />
              </Field>
            </div>
            <Field label="Category" htmlFor="ev-cat">
              <CategoryPicker id="ev-cat" value={categoryId} onChange={(c) => setCategoryId(c?.id ?? null)} placeholder="Optional" direction="debit" />
            </Field>
            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!title.trim() || !(toNumber(amount) > 0)} loading={add.isPending}>
                Add one-off
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

/* ---------------- empty state: generate ---------------- */

function GenerateCard({ month, label }: { month: string; label: string }) {
  const generate = useGeneratePlan(month);
  const [needsIncome, setNeedsIncome] = useState(false);
  const [income, setIncome] = useState("");

  function run() {
    generate.mutate(needsIncome ? { expected_income: income } : undefined, {
      onSuccess: () => toast.success(`${label} plan drafted`),
      onError: (err) => {
        if (errorCode(err) === "INCOME_REQUIRED") setNeedsIncome(true);
        else toast.error(errorMessage(err));
      },
    });
  }

  return (
    <Card className="overflow-hidden">
      <div className="grid lg:grid-cols-[1.1fr_1fr]">
        <div className="p-7 sm:p-10">
          <span className="grid size-11 place-items-center rounded-xl bg-brand-soft text-brand-ink">
            <WandSparkles className="size-5" />
          </span>
          <h2 className="mt-5 text-2xl font-semibold tracking-[-0.03em]">Build your {label} plan</h2>
          <p className="mt-2 max-w-md text-[15px] leading-relaxed text-text-2">
            Spendzer drafts a budget from your own history. You edit any number, then activate it to track the month.
          </p>
          {needsIncome && (
            <div className="mt-6 max-w-xs">
              <Field label="Expected income this month" htmlFor="gen-income" hint="We couldn't find income in your statements yet.">
                <MoneyInput id="gen-income" value={income} onChange={setIncome} />
              </Field>
            </div>
          )}
          <Button className="mt-7" size="lg" variant="brand" loading={generate.isPending} disabled={needsIncome && !(toNumber(income) > 0)} onClick={run}>
            Draft my plan <ArrowRight />
          </Button>
        </div>
        <ol className="grid gap-px border-t border-border bg-border lg:border-l lg:border-t-0">
          {[
            { t: "Savings first", d: "Your savings target comes off the top — before any spending." },
            { t: "Fixed costs", d: "Rent, EMIs and subscriptions we detected as recurring." },
            { t: "Forecasts", d: "Everything else, from the median of your last three months." },
            { t: "Fit check", d: "If it doesn't fit, we suggest cuts. Never to your savings." },
          ].map((s, i) => (
            <li key={s.t} className="flex gap-4 bg-surface px-7 py-4">
              <span className="tabular grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-semibold">{i + 1}</span>
              <div>
                <p className="text-sm font-semibold">{s.t}</p>
                <p className="text-[13px] text-text-3">{s.d}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}

/* ---------------- page ---------------- */

export default function PlannerPage() {
  const { month = defaultPlanMonth() } = useParams();
  const navigate = useNavigate();
  const valid = /^\d{4}-\d{2}$/.test(month);
  const monthDate = parseISODate(`${valid ? month : defaultPlanMonth()}-01`);
  const label = formatMonthLong(monthDate).split(" ")[0];
  const { data: plan, isLoading } = usePlan(month);
  const generate = useGeneratePlan(month);
  const activate = useActivatePlan(month, plan?.id ?? "");

  const sections = useMemo(() => {
    const items = plan?.items ?? [];
    const fixed = items.filter((i) => i.source === "fixed" || i.bucket === "fixed");
    const rest = items.filter((i) => !fixed.includes(i));
    return {
      fixed,
      variable: rest.filter((i) => i.bucket === "variable"),
      discretionary: rest.filter((i) => i.bucket !== "variable"),
    };
  }, [plan]);

  if (!valid) return <Navigate to={`/plan/${defaultPlanMonth()}`} replace />;

  const statusBadge = plan && (
    <Badge tone={plan.status === "active" ? "good" : plan.status === "draft" ? "warning" : "neutral"} className="px-2.5 py-1 text-xs">
      {plan.status === "active" ? <CircleCheck /> : null}
      {plan.status === "active" ? "Active" : plan.status === "draft" ? "Draft" : "Closed"}
    </Badge>
  );

  return (
    <div className="animate-fade-up">
      <PageHeader
        title={`${label} plan`}
        description={plan ? "Savings first, then a job for every rupee." : "Know where it's going before it goes."}
        actions={
          <>
            {statusBadge}
            <MonthSwitcher month={monthDate} maxAhead={2} onChange={(d) => navigate(`/plan/${monthKey(d)}`)} />
            {plan?.status === "closed" && (
              <Button asChild variant="brand">
                <Link to={`/review/${month}`}>
                  <ClipboardCheck /> See the review
                </Link>
              </Button>
            )}
            {plan?.status === "draft" && (
              <>
                <Tooltip content="Re-run forecasts with your latest data. Your own edits are kept.">
                  <Button
                    variant="secondary"
                    loading={generate.isPending}
                    onClick={() => generate.mutate(undefined, { onSuccess: () => toast.success("Plan refreshed") })}
                  >
                    <RefreshCw /> Refresh
                  </Button>
                </Tooltip>
                <Button
                  variant="brand"
                  loading={activate.isPending}
                  onClick={() =>
                    activate.mutate(undefined, {
                      onSuccess: () => toast.success(`${label} plan is live`, { description: "Track it from your dashboard." }),
                      onError: (err) => toast.error(errorMessage(err)),
                    })
                  }
                >
                  <Rocket /> Activate plan
                </Button>
              </>
            )}
          </>
        }
      />

      {isLoading ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <Skeleton className="h-72 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      ) : !plan ? (
        <GenerateCard month={month} label={label} />
      ) : (
        <div className="grid gap-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
            <IncomeCard plan={plan} month={month} />
            <FitCheck plan={plan} month={month} />
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="Fixed costs" description="Recurring charges — never cut" items={sections.fixed} plan={plan} month={month} allowAdd addBuckets={["fixed"]} />
            <Section title="Everyday" description="Groceries, transport, bills" items={sections.variable} plan={plan} month={month} allowAdd addBuckets={["variable"]} />
            <Section title="Lifestyle" description="Eating out, shopping, fun" items={sections.discretionary} plan={plan} month={month} allowAdd addBuckets={["discretionary"]} />
            <EventsCard plan={plan} month={month} />
          </div>
        </div>
      )}
    </div>
  );
}
