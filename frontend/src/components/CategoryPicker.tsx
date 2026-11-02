import { Check, ChevronsUpDown, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { useCategories } from "@/api/queries";
import type { Bucket, Category } from "@/api/types";
import { CategoryDot } from "@/components/common";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { cn } from "@/lib/utils";

const BUCKET_LABEL: Record<Bucket, string> = {
  discretionary: "Lifestyle",
  variable: "Everyday",
  fixed: "Fixed costs",
  income: "Income",
  excluded: "Not counted",
};
const ORDER: Bucket[] = ["discretionary", "variable", "fixed", "income", "excluded"];

export function CategoryList({
  value,
  onSelect,
  direction,
}: {
  value?: string | null;
  onSelect: (category: Category) => void;
  direction?: "debit" | "credit";
}) {
  const { data: categories = [] } = useCategories();
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    // Credits list income first; debits list spending first.
    const order = direction === "credit" ? (["income", "excluded", "discretionary", "variable", "fixed"] as Bucket[]) : ORDER;
    return order
      .map((bucket) => ({
        bucket,
        items: categories
          .filter((c) => c.bucket === bucket && (!q || c.name.toLowerCase().includes(q)))
          .sort((a, b) => a.name.localeCompare(b.name)),
      }))
      .filter((g) => g.items.length);
  }, [categories, query, direction]);

  return (
    <div className="w-72">
      <div className="flex items-center gap-2 border-b border-border px-2.5 pb-2 pt-1.5">
        <Search className="size-4 text-text-3" />
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search categories"
          className="h-8 w-full bg-transparent text-sm outline-none placeholder:text-text-3"
        />
      </div>
      <div className="max-h-80 overflow-y-auto p-1">
        {groups.length === 0 && <p className="px-3 py-6 text-center text-sm text-text-3">No categories match</p>}
        {groups.map((g) => (
          <div key={g.bucket} className="py-1">
            <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-[0.06em] text-text-3">
              {BUCKET_LABEL[g.bucket]}
            </p>
            {g.items.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelect(c)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-surface-2",
                  c.id === value && "bg-surface-2",
                )}
              >
                <CategoryDot category={c} size="sm" />
                <span className="flex-1 truncate">{c.name}</span>
                {c.id === value && <Check className="size-4 text-brand" />}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Form field: a button that opens the category list. */
export function CategoryPicker({
  value,
  onChange,
  direction,
  placeholder = "Auto-detect",
  id,
}: {
  value: string | null;
  onChange: (category: Category | null) => void;
  direction?: "debit" | "credit";
  placeholder?: string;
  id?: string;
}) {
  const { data: categories = [] } = useCategories();
  const [open, setOpen] = useState(false);
  const selected = categories.find((c) => c.id === value) ?? null;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        id={id}
        className="flex h-10 w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 text-left text-sm shadow-[var(--shadow-card)] transition-colors hover:border-border-strong focus-visible:border-brand focus-visible:shadow-[0_0_0_3px_var(--ring)] focus-visible:outline-none"
      >
        {selected ? (
          <>
            <CategoryDot category={selected} size="sm" />
            <span className="flex-1 truncate">{selected.name}</span>
          </>
        ) : (
          <span className="flex-1 text-text-3">{placeholder}</span>
        )}
        <ChevronsUpDown className="size-4 text-text-3" />
      </PopoverTrigger>
      <PopoverContent className="p-0">
        <CategoryList
          value={value}
          direction={direction}
          onSelect={(c) => {
            onChange(c);
            setOpen(false);
          }}
        />
        {selected && (
          <div className="border-t border-border p-1">
            <button
              type="button"
              onClick={() => {
                onChange(null);
                setOpen(false);
              }}
              className="w-full rounded-lg px-2.5 py-2 text-left text-sm text-text-2 hover:bg-surface-2"
            >
              Let Spendzer decide
            </button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
