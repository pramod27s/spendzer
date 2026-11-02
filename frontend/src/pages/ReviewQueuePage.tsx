import { ArrowLeftRight, Briefcase, CircleCheck, CircleHelp, Coins, HandCoins, History, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useBulkCategorize, useCategories, useReviewQueue, useUpdateTransaction } from "@/api/queries";
import type { Category, PayeeStats, Transaction } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { CategoryList } from "@/components/CategoryPicker";
import { Amount, CategoryDot, EmptyState } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { formatDay, formatINR, formatTime, toNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

// The categories people pick most for stray spends, offered as one-tap chips.
const QUICK_SPEND = ["Food & Dining", "Groceries", "Transport", "Shopping", "Personal Care", "Gifts & Donations"];
const SMALL_SPENDS = "Small Spends";
/** Payments at or under this go first to "Small Spends" and into the one-tap bulk action. */
const SMALL_LIMIT = 100;

const TIME_LABEL = { morning: "mornings", afternoon: "afternoons", evening: "evenings", night: "late nights" } as const;

function useByName() {
  const { data = [] } = useCategories();
  return useMemo(() => new Map(data.filter((c) => c.is_system).map((c) => [c.name, c])), [data]);
}

function Narration({ txn }: { txn: Transaction }) {
  return <p className="truncate font-mono text-[11px] text-text-3">{txn.raw_description}</p>;
}

/** "Paid 6x since 20 Oct, usually Rs 20-40, mostly mornings": a memory jog for who this was. */
function PayeeHint({ stats }: { stats?: PayeeStats }) {
  if (!stats) return null;
  if (stats.count < 2) {
    return <p className="mt-1 text-xs text-text-3">Only payment to this person so far</p>;
  }
  const lo = toNumber(stats.min_amount);
  const hi = toNumber(stats.max_amount);
  const range = lo === hi ? formatINR(lo) : `${formatINR(lo)}–${formatINR(hi)}`;
  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs text-brand-ink">
      <History className="size-3" />
      Paid {stats.count}× since {formatDay(stats.first_date)}
      <span className="text-text-3">·</span> usually {range}
      {stats.usual_time && (
        <>
          <span className="text-text-3">·</span> mostly {TIME_LABEL[stats.usual_time]}
        </>
      )}
    </p>
  );
}

interface PayeeGroup {
  key: string;
  merchant: string;
  txns: Transaction[];
  total: number;
}

/** One card per payee: answer once and every payment to them is sorted. */
function PayeeCard({ group, stats }: { group: PayeeGroup; stats?: PayeeStats }) {
  const byName = useByName();
  const update = useUpdateTransaction();
  const [open, setOpen] = useState(false);
  const [first] = group.txns;
  const many = group.txns.length > 1;
  const typical = group.total / group.txns.length;
  const small = typical <= SMALL_LIMIT;
  // Small payments lead with "Small Spends"; everything else keeps it at the end.
  const quick = small ? [SMALL_SPENDS, ...QUICK_SPEND] : [...QUICK_SPEND, SMALL_SPENDS];
  const named = !!group.merchant;

  async function choose(cat: Category) {
    try {
      // With a payee, one PATCH + apply_to_merchant sorts every payment to them (and future ones).
      await update.mutateAsync({ id: first.id, category_id: cat.id, apply_to_merchant: named });
      toast.success(`${group.merchant || "Payment"} → ${cat.name}`, {
        description: named ? "Every payment to them is sorted, now and in future statements." : undefined,
      });
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function notSure() {
    const other = byName.get("Other");
    if (!other) return;
    try {
      // Hand-setting "Other" takes the payee off this list without guessing a category.
      await update.mutateAsync({ id: first.id, category_id: other.id, apply_to_merchant: named });
      toast.success(named ? `Won't ask about ${group.merchant} again` : "Skipped — left in Other", {
        description: "It still counts in your spending. Change it any time from Transactions.",
      });
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <li className="flex flex-col rounded-xl border border-border p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{group.merchant || "Unknown merchant"}</p>
          <PayeeHint stats={stats} />
        </div>
        <div className="text-right">
          <Amount value={group.total} direction="debit" className="text-[15px]" />
          {many && <p className="text-[11px] text-text-3">{group.txns.length} payments</p>}
        </div>
      </div>
      <ul className="mt-2.5 flex flex-wrap gap-1.5">
        {group.txns.slice(0, 6).map((t) => (
          <li key={t.id} className="rounded-md bg-surface-2 px-2 py-1 text-[11.5px] text-text-2" title={t.raw_description}>
            {formatDay(t.txn_date)}
            {t.txn_time && ` · ${formatTime(t.txn_time)}`}
            <span className="tabular ml-1.5 font-medium text-text">{formatINR(t.amount)}</span>
          </li>
        ))}
        {group.txns.length > 6 && <li className="px-1 py-1 text-[11.5px] text-text-3">+{group.txns.length - 6} more</li>}
      </ul>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {quick.map((name) => {
          const cat = byName.get(name);
          if (!cat) return null;
          return (
            <button
              key={name}
              type="button"
              disabled={update.isPending}
              onClick={() => void choose(cat)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border py-1 pl-1 pr-2.5 text-xs transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-text disabled:opacity-50",
                small && name === SMALL_SPENDS ? "border-brand/40 bg-brand-soft text-brand-ink" : "border-border text-text-2",
              )}
            >
              <CategoryDot category={cat} size="sm" /> {name}
            </button>
          );
        })}
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <button type="button" className="rounded-full border border-dashed border-border-strong px-3 py-1 text-xs text-text-2 hover:bg-surface-2">
              More…
            </button>
          </PopoverTrigger>
          <PopoverContent className="p-0">
            <CategoryList
              direction="debit"
              onSelect={(c) => {
                setOpen(false);
                void choose(c);
              }}
            />
          </PopoverContent>
        </Popover>
      </div>
      <button
        type="button"
        disabled={update.isPending}
        onClick={() => void notSure()}
        className="mt-2.5 inline-flex w-fit items-center gap-1 text-xs text-text-3 hover:text-text"
      >
        <CircleHelp className="size-3.5" /> Not sure — {many ? "skip all of these" : "skip"}
      </button>
    </li>
  );
}

function groupByPayee(txns: Transaction[]): PayeeGroup[] {
  const groups = new Map<string, PayeeGroup>();
  for (const t of txns) {
    const key = t.merchant || `id:${t.id}`;
    const g = groups.get(key) ?? { key, merchant: t.merchant, txns: [], total: 0 };
    g.txns.push(t);
    g.total += toNumber(t.amount);
    groups.set(key, g);
  }
  // Payees you pay most (by total) first: sorting them clears the most money.
  return [...groups.values()].sort((a, b) => b.total - a.total);
}

/** One tap to file every small payment, instead of thirty. */
function SmallPaymentsBanner({ items }: { items: Transaction[] }) {
  const byName = useByName();
  const bulk = useBulkCategorize();
  const small = items.filter((t) => toNumber(t.amount) <= SMALL_LIMIT);
  const target = byName.get(SMALL_SPENDS);
  if (small.length < 2 || !target) return null;
  const total = small.reduce((sum, t) => sum + toNumber(t.amount), 0);
  return (
    <div className="mx-4 mt-3 flex flex-col gap-3 rounded-xl border border-brand/25 bg-brand-soft/60 p-3.5 sm:flex-row sm:items-center">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface text-brand-ink">
        <Coins className="size-4" />
      </span>
      <p className="flex-1 text-[13px] text-text-2">
        <span className="font-semibold text-text">{small.length} small payments</span> of {formatINR(SMALL_LIMIT)} or less ({formatINR(total)} in all) — autos, tea, snacks, small shops.
        File them together?
      </p>
      <Button
        size="sm"
        loading={bulk.isPending}
        onClick={() =>
          bulk.mutate(
            { transaction_ids: small.map((t) => t.id), category_id: target.id },
            {
              onSuccess: (r) => toast.success(`${r.updated} payments filed under Small Spends`, { description: "Change any of them later from Transactions." }),
              onError: (err) => toast.error(errorMessage(err)),
            },
          )
        }
      >
        File as Small Spends
      </Button>
    </div>
  );
}

function CreditRow({ txn }: { txn: Transaction }) {
  const byName = useByName();
  const update = useUpdateTransaction();

  const answers: { label: string; icon: typeof Briefcase; category: string; note: string }[] = [
    { label: "Salary", icon: Briefcase, category: "Salary", note: "Counted as income" },
    { label: "Freelance", icon: HandCoins, category: "Freelance", note: "Counted as income" },
    { label: "Pocket money", icon: HandCoins, category: "Pocket Money", note: "Counted as income" },
    { label: "From my own account", icon: ArrowLeftRight, category: "Self Transfer", note: "Not counted" },
    { label: "Refund / paid back", icon: Undo2, category: "Refund", note: "Not counted" },
  ];

  async function answer(categoryName: string, note: string) {
    const cat = byName.get(categoryName);
    if (!cat) return;
    try {
      await update.mutateAsync({ id: txn.id, category_id: cat.id, apply_to_merchant: !!txn.merchant });
      toast.success(`${txn.merchant || "Credit"}: ${categoryName}`, {
        description: `${note}. We'll remember this for ${txn.merchant || "this sender"}.`,
      });
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <li className="px-4 py-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{txn.merchant || "Unknown sender"}</p>
          <p className="text-xs text-text-3">{formatDay(txn.txn_date, true)}</p>
          <Narration txn={txn} />
        </div>
        <Amount value={txn.amount} direction="credit" className="text-[15px]" />
      </div>
      <p className="mt-3 text-[13px] font-medium text-text-2">Is this income?</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {answers.map((a) => (
          <Button
            key={a.label}
            size="sm"
            variant={a.note === "Counted as income" ? "secondary" : "ghost"}
            disabled={update.isPending}
            onClick={() => void answer(a.category, a.note)}
          >
            <a.icon /> {a.label}
          </Button>
        ))}
      </div>
    </li>
  );
}

export default function ReviewQueuePage() {
  const { data, isLoading } = useReviewQueue();
  const groups = useMemo(() => groupByPayee(data?.uncategorized ?? []), [data]);
  const credits = data?.unknown_credits ?? [];

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Review"
        description="A few things Spendzer couldn't figure out on its own. Each answer teaches it for next time."
      />
      {isLoading ? (
        <Skeleton className="h-72 rounded-2xl" />
      ) : !data || data.total === 0 ? (
        <Card>
          <EmptyState icon={CircleCheck} title="All caught up" description="Every spend has a category and every credit is explained." />
        </Card>
      ) : (
        <div className="grid gap-5">
          {credits.length > 0 && (
            <Card>
              <CardHeader
                title="Is this income?"
                description={`${credits.length} ${credits.length === 1 ? "credit" : "credits"} we couldn't explain — they don't count as income until you say so`}
              />
              <ul className="divide-y divide-border pt-2">
                {credits.map((t) => (
                  <CreditRow key={t.id} txn={t} />
                ))}
              </ul>
            </Card>
          )}
          {groups.length > 0 && (
            <Card>
              <CardHeader
                title="Who did you pay?"
                description={`${data.uncategorized.length} ${data.uncategorized.length === 1 ? "payment" : "payments"} to ${groups.length} ${groups.length === 1 ? "payee" : "payees"} filed under Other — answer once per payee and future payments follow`}
              />
              <SmallPaymentsBanner items={data.uncategorized} />
              <ul className="grid gap-3 p-4 lg:grid-cols-2">
                {groups.map((g) => (
                  <PayeeCard key={g.key} group={g} stats={g.merchant ? data.payee_stats[g.merchant] : undefined} />
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
