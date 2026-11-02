import {
  ArrowUpDown,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Filter,
  Plus,
  Search,
  Sparkles,
  Trash2,
  WandSparkles,
  Copy,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useAccounts, useDeleteTransaction, useTransactions, useUpdateTransaction } from "@/api/queries";
import type { Category, Transaction, TransactionFilters, TxnKind } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { CategoryList } from "@/components/CategoryPicker";
import { Amount, CategoryDot, EmptyState, MerchantAvatar, UploadCta } from "@/components/common";
import { ManualEntryDialog } from "@/components/ManualEntryDialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger, Tooltip } from "@/components/ui/overlays";
import { Badge, Card, Field, Input, Skeleton } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatDay, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

const KIND_META: Record<TxnKind, { label: string; tone: "neutral" | "good" | "warning" | "brand" }> = {
  expense: { label: "Spending", tone: "neutral" },
  income: { label: "Income", tone: "good" },
  refund: { label: "Refund", tone: "neutral" },
  cashback: { label: "Cashback", tone: "neutral" },
  self_transfer: { label: "Self-transfer", tone: "neutral" },
  investment: { label: "Investment", tone: "brand" },
  unknown: { label: "Unconfirmed credit", tone: "warning" },
};

const KIND_OPTIONS = [
  { value: "all", label: "All types" },
  ...(Object.keys(KIND_META) as TxnKind[]).map((k) => ({ value: k, label: KIND_META[k].label })),
];

const FILTER_KEYS = ["search", "category_id", "kind", "account_id", "start", "end", "merchant", "direction"] as const;

function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters: TransactionFilters = useMemo(() => {
    const f: TransactionFilters = { page: Number(params.get("page") ?? 1) || 1, size: PAGE_SIZE };
    for (const k of FILTER_KEYS) {
      const v = params.get(k);
      if (v) (f as Record<string, unknown>)[k] = v;
    }
    return f;
  }, [params]);

  const update = (patch: Partial<Record<(typeof FILTER_KEYS)[number] | "page", string | undefined>>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };
  const clear = () => setParams({}, { replace: true });
  const active = FILTER_KEYS.filter((k) => params.get(k) && k !== "search").length;
  return { filters, update, clear, active };
}

/* ---------- Category cell with "apply to all?" prompt ---------- */

function CategoryCell({ txn, category }: { txn: Transaction; category: Category | null | undefined }) {
  const update = useUpdateTransaction();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<Category | null>(null);

  async function save(cat: Category, applyAll: boolean) {
    try {
      const res = await update.mutateAsync({ id: txn.id, category_id: cat.id, apply_to_merchant: applyAll });
      toast.success(
        applyAll && res.recategorized > 0
          ? `${res.recategorized + 1} ${txn.merchant} transactions moved to ${cat.name}`
          : `Moved to ${cat.name}`,
        applyAll ? { description: `Future ${txn.merchant} payments will land here too.` } : undefined,
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setPending(null);
    }
  }

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          className="group/cat inline-flex max-w-full items-center gap-2 rounded-lg py-1 pl-1 pr-2 text-left transition-colors hover:bg-surface-2"
          onClick={(e) => e.stopPropagation()}
          aria-label={`Change category for ${txn.merchant || "transaction"}`}
        >
          <CategoryDot category={category} size="sm" />
          <span className="truncate text-[13px] text-text-2">{category?.name ?? "Uncategorized"}</span>
          {txn.categorized_by === "override" && (
            <Tooltip content="Sorted by one of your rules">
              <Sparkles className="size-3 shrink-0 text-brand" />
            </Tooltip>
          )}
          {txn.categorized_by === "ml" && (
            <Tooltip content="Sorted by Spendzer's model — no rule knew this merchant. Change it to teach it.">
              <WandSparkles className="size-3 shrink-0 text-brand" />
            </Tooltip>
          )}
          <ChevronDown className="size-3.5 shrink-0 text-text-3 opacity-0 transition-opacity group-hover/cat:opacity-100" />
        </PopoverTrigger>
        <PopoverContent className="p-0" onClick={(e) => e.stopPropagation()}>
          <CategoryList
            value={txn.category_id}
            direction={txn.direction}
            onSelect={(cat) => {
              setOpen(false);
              if (cat.id === txn.category_id) return;
              if (txn.merchant) setPending(cat);
              else void save(cat, false);
            }}
          />
        </PopoverContent>
      </Popover>

      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent
          title={`Apply to all transactions from ${txn.merchant}?`}
          description={`Move every ${txn.merchant} transaction to ${pending?.name}, and sort future ones there automatically. Rows you've set by hand stay as they are.`}
        >
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={() => pending && save(pending, false)} disabled={update.isPending}>
              Just this one
            </Button>
            <Button onClick={() => pending && save(pending, true)} loading={update.isPending}>
              <Sparkles /> Apply to all
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ---------- Detail dialog ---------- */

function TransactionDetail({ txn, onClose, accountName }: { txn: Transaction | null; onClose: () => void; accountName: (id: string) => string }) {
  const update = useUpdateTransaction();
  const remove = useDeleteTransaction();
  const categories = useCategoryMap();
  const [note, setNote] = useState("");
  const [kind, setKind] = useState<TxnKind>("expense");

  useEffect(() => {
    if (txn) {
      setNote(txn.note ?? "");
      setKind(txn.kind);
    }
  }, [txn]);

  if (!txn) return null;
  const category = txn.category_id ? categories.get(txn.category_id) : null;
  const dirty = note !== (txn.note ?? "") || kind !== txn.kind;

  async function save() {
    if (!txn) return;
    try {
      await update.mutateAsync({ id: txn.id, note: note || null, ...(kind !== txn.kind ? { kind } : {}) });
      toast.success("Saved");
      onClose();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={txn.merchant || "Transaction"} description={`${formatDay(txn.txn_date, true)} · ${accountName(txn.account_id)}`}>
        <div className="grid gap-5">
          <div className="flex items-center justify-between rounded-xl bg-surface-2/70 px-4 py-3.5">
            <div className="flex items-center gap-3">
              <CategoryDot category={category} size="lg" />
              <div>
                <p className="text-sm font-medium">{category?.name ?? "Uncategorized"}</p>
                <p className="text-xs text-text-3">
                  {txn.categorized_by === "user" ? "Set by you" : txn.categorized_by === "override" ? "Your rule" : "Auto-detected"}
                </p>
              </div>
            </div>
            <Amount value={txn.amount} direction={txn.direction} className="text-xl font-semibold" />
          </div>
          {txn.upload_id && (
            <div>
              <p className="mb-1.5 text-[13px] font-medium text-text-2">Bank narration</p>
              <p className="break-all rounded-lg border border-border bg-surface-2/40 px-3 py-2 font-mono text-[12px] text-text-2">
                {txn.raw_description}
              </p>
            </div>
          )}
          <Field label="Counts as" htmlFor="td-kind" hint="Only spending and income count towards your totals.">
            <Select
              id="td-kind"
              value={kind}
              onValueChange={(v) => setKind(v as TxnKind)}
              options={(Object.keys(KIND_META) as TxnKind[]).map((k) => ({ value: k, label: KIND_META[k].label }))}
            />
          </Field>
          <Field label="Note" htmlFor="td-note">
            <Input id="td-note" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} placeholder="Add a note" />
          </Field>
          <div className="flex items-center justify-between gap-2">
            {txn.upload_id === null ? (
              <Button
                variant="ghost"
                className="text-critical-ink hover:bg-critical-soft hover:text-critical-ink"
                loading={remove.isPending}
                onClick={async () => {
                  try {
                    await remove.mutateAsync(txn.id);
                    toast.success("Entry deleted");
                    onClose();
                  } catch (err) {
                    toast.error(errorMessage(err));
                  }
                }}
              >
                <Trash2 /> Delete
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
              <Button onClick={save} disabled={!dirty} loading={update.isPending}>
                Save
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ---------- Page ---------- */

export default function TransactionsPage() {
  const { filters, update, clear, active } = useFilters();
  const { data, isLoading, isFetching } = useTransactions(filters);
  const { data: accounts = [] } = useAccounts();
  const categories = useCategoryMap();
  const [search, setSearch] = useState(filters.search ?? "");
  const [manualOpen, setManualOpen] = useState(false);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [catFilterOpen, setCatFilterOpen] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => {
      if ((filters.search ?? "") !== search.trim()) update({ search: search.trim() || undefined });
    }, 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const accountName = (id: string) => accounts.find((a) => a.id === id)?.name ?? "Account";
  const page = filters.page ?? 1;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const filterCategory = filters.category_id ? categories.get(filters.category_id) : null;
  const noData = !isLoading && data?.total === 0 && !active && !filters.search;

  const chips: { key: (typeof FILTER_KEYS)[number]; label: string }[] = [];
  if (filters.start || filters.end)
    chips.push({ key: "start", label: `${filters.start ? formatDay(filters.start) : "…"} – ${filters.end ? formatDay(filters.end, true) : "…"}` });
  if (filters.merchant) chips.push({ key: "merchant", label: filters.merchant });
  if (filters.direction) chips.push({ key: "direction", label: filters.direction === "debit" ? "Money out" : "Money in" });

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Transactions"
        description={data ? `${data.total.toLocaleString("en-IN")} transactions${active || filters.search ? " match your filters" : ""}` : "Every rupee in and out."}
        actions={
          <Button onClick={() => setManualOpen(true)}>
            <Plus /> Cash entry
          </Button>
        }
      />
      <ManualEntryDialog open={manualOpen} onOpenChange={setManualOpen} />
      <TransactionDetail txn={selected} onClose={() => setSelected(null)} accountName={accountName} />

      {noData ? (
        <Card>
          <EmptyState title="No transactions yet" description="Upload a bank statement or add a cash entry to get started." action={<UploadCta />} />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          {/* Toolbar */}
          <div className="flex flex-col gap-3 border-b border-border p-3 sm:p-4 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-3" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search merchant, narration or note" className="pl-9" aria-label="Search transactions" />
            </div>
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <Popover open={catFilterOpen} onOpenChange={setCatFilterOpen}>
                <PopoverTrigger asChild>
                  <Button variant="secondary" className="h-10 justify-start">
                    {filterCategory ? <CategoryDot category={filterCategory} size="sm" /> : <Filter />}
                    <span className="truncate">{filterCategory?.name ?? "Category"}</span>
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0">
                  <CategoryList
                    value={filters.category_id}
                    onSelect={(c) => {
                      update({ category_id: c.id });
                      setCatFilterOpen(false);
                    }}
                  />
                </PopoverContent>
              </Popover>
              <Select
                value={filters.kind ?? "all"}
                onValueChange={(v) => update({ kind: v === "all" ? undefined : v })}
                options={KIND_OPTIONS}
                className="sm:w-44"
                aria-label="Type"
              />
              <Select
                value={filters.account_id ?? "all"}
                onValueChange={(v) => update({ account_id: v === "all" ? undefined : v })}
                options={[{ value: "all", label: "All accounts" }, ...accounts.map((a) => ({ value: a.id, label: a.name }))]}
                className="col-span-2 sm:w-44"
                aria-label="Account"
              />
            </div>
          </div>

          {(active > 0 || chips.length > 0) && (
            <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
              {chips.map((c) => (
                <button
                  key={c.key}
                  onClick={() => update(c.key === "start" ? { start: undefined, end: undefined } : { [c.key]: undefined })}
                  className="inline-flex items-center gap-1 rounded-full bg-surface-2 py-1 pl-2.5 pr-1.5 text-xs text-text-2 hover:bg-surface-3"
                >
                  {c.label} <X className="size-3.5" />
                </button>
              ))}
              <Button variant="link" size="sm" className="ml-auto h-auto text-xs" onClick={clear}>
                Clear all
              </Button>
            </div>
          )}

          {/* Desktop table */}
          <div className={cn("hidden md:block", isFetching && !isLoading && "opacity-70 transition-opacity")}>
            <table className="w-full table-fixed text-left text-sm">
              <thead>
                <tr className="text-xs text-text-3">
                  <th className="w-[92px] px-4 py-2.5 font-medium">Date</th>
                  <th className="px-4 py-2.5 font-medium">Merchant</th>
                  <th className="w-[220px] px-4 py-2.5 font-medium">Category</th>
                  <th className="hidden w-[150px] px-4 py-2.5 font-medium xl:table-cell">Account</th>
                  <th className="w-[140px] px-4 py-2.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-t border-border">
                        <td colSpan={5} className="px-4 py-3">
                          <Skeleton className="h-6" />
                        </td>
                      </tr>
                    ))
                  : data?.items.map((t) => {
                      const cat = t.category_id ? categories.get(t.category_id) : null;
                      const excluded = (t.kind !== "expense" && t.kind !== "income") || !!t.dedup_of;
                      return (
                        <tr
                          key={t.id}
                          onClick={() => setSelected(t)}
                          className="cursor-pointer border-t border-border transition-colors hover:bg-surface-2/50"
                        >
                          <td className="tabular px-4 py-2.5 text-[13px] text-text-2">
                            {formatDay(t.txn_date)}
                            {t.txn_time && <span className="block text-[11px] text-text-3">{formatTime(t.txn_time)}</span>}
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex min-w-0 items-center gap-3">
                              <MerchantAvatar name={t.merchant || "?"} category={null} />
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="truncate font-medium">{t.merchant || "Unknown"}</p>
                                  {t.dedup_of ? (
                                    <Tooltip content="The same payment is in another statement you uploaded. It's counted once, there.">
                                      <Badge tone="outline">
                                        <Copy /> Duplicate
                                      </Badge>
                                    </Tooltip>
                                  ) : (
                                    t.kind !== "expense" && <Badge tone={KIND_META[t.kind].tone}>{KIND_META[t.kind].label}</Badge>
                                  )}
                                </div>
                                <p className="truncate font-mono text-[11px] text-text-3">{t.note || t.raw_description}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <CategoryCell txn={t} category={cat} />
                          </td>
                          <td className="hidden truncate px-4 py-2.5 text-[13px] text-text-2 xl:table-cell">{accountName(t.account_id)}</td>
                          <td className="px-4 py-2.5 text-right">
                            <Amount value={t.amount} direction={t.direction} className={cn(excluded && "text-text-3", t.dedup_of && "line-through")} />
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          </div>

          {/* Mobile list */}
          <ul className="md:hidden">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <li key={i} className="border-t border-border p-4 first:border-t-0">
                    <Skeleton className="h-10" />
                  </li>
                ))
              : data?.items.map((t) => {
                  const cat = t.category_id ? categories.get(t.category_id) : null;
                  return (
                    <li key={t.id} className="border-t border-border first:border-t-0">
                      <div className="flex items-start gap-3 px-4 py-3" onClick={() => setSelected(t)}>
                        <MerchantAvatar name={t.merchant || "?"} category={cat} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline justify-between gap-2">
                            <p className="truncate text-sm font-medium">{t.merchant || "Unknown"}</p>
                            <Amount value={t.amount} direction={t.direction} className="text-sm" />
                          </div>
                          <div className="mt-0.5 flex items-center justify-between gap-2">
                            <CategoryCell txn={t} category={cat} />
                            <span className="shrink-0 text-xs text-text-3">{formatDay(t.txn_date)}</span>
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
          </ul>

          {!isLoading && data?.items.length === 0 && (
            <EmptyState compact icon={ArrowUpDown} title="Nothing matches" description="Try a different search or clear the filters." action={<Button variant="secondary" onClick={clear}>Clear filters</Button>} />
          )}

          {data && data.total > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-text-2">
              <span className="tabular">
                {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total.toLocaleString("en-IN")}
              </span>
              <div className="flex gap-1">
                <Button variant="secondary" size="icon-sm" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })} aria-label="Previous page">
                  <ChevronLeft />
                </Button>
                <Button variant="secondary" size="icon-sm" disabled={page >= totalPages} onClick={() => update({ page: String(page + 1) })} aria-label="Next page">
                  <ChevronRight />
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
      {data && data.items.length > 0 && (
        <p className="mt-3 text-center text-xs text-text-3">
          Tip: change a category and Spendzer offers to remember it for that merchant.
        </p>
      )}
    </div>
  );
}
