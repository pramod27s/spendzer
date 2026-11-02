import { CalendarRange, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import type { PeriodName, PeriodQuery } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { Field, Input } from "@/components/ui/primitives";
import { Segmented } from "@/components/ui/select";
import { addMonths, formatDay, formatMonthLong } from "@/lib/format";

export function MonthSwitcher({
  month,
  onChange,
  maxAhead = 0,
}: {
  month: Date;
  onChange: (d: Date) => void;
  maxAhead?: number;
}) {
  const limit = addMonths(new Date(), maxAhead);
  const atLatest = month.getFullYear() * 12 + month.getMonth() >= limit.getFullYear() * 12 + limit.getMonth();
  return (
    <div className="inline-flex items-center rounded-xl border border-border bg-surface shadow-[var(--shadow-card)]">
      <Button variant="ghost" size="icon-sm" onClick={() => onChange(addMonths(month, -1))} aria-label="Previous month">
        <ChevronLeft />
      </Button>
      <span className="tabular min-w-[132px] px-1 text-center text-sm font-medium">{formatMonthLong(month)}</span>
      <Button variant="ghost" size="icon-sm" onClick={() => onChange(addMonths(month, 1))} disabled={atLatest} aria-label="Next month">
        <ChevronRight />
      </Button>
    </div>
  );
}

const PRESETS: { value: Exclude<PeriodName, "custom">; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "last_3", label: "3M" },
  { value: "last_6", label: "6M" },
  { value: "last_12", label: "12M" },
];

export function PeriodPicker({ value, onChange }: { value: PeriodQuery; onChange: (q: PeriodQuery) => void }) {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState(value.start ?? "");
  const [end, setEnd] = useState(value.end ?? "");
  const custom = value.period === "custom";
  const valid = !!start && !!end && start <= end;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented
        value={custom ? ("custom" as PeriodName) : value.period}
        onChange={(p) => p !== "custom" && onChange({ ...value, period: p, start: undefined, end: undefined })}
        options={PRESETS}
        className="max-w-full overflow-x-auto scrollbar-none"
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant={custom ? "primary" : "secondary"} size="sm" className="h-[34px]">
            <CalendarRange />
            {custom && value.start && value.end ? `${formatDay(value.start)} – ${formatDay(value.end, true)}` : "Custom"}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-72 p-4">
          <div className="grid gap-3">
            <Field label="From" htmlFor="p-start">
              <Input id="p-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field label="To" htmlFor="p-end">
              <Input id="p-end" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />
            </Field>
            <Button
              disabled={!valid}
              onClick={() => {
                onChange({ ...value, period: "custom", start, end });
                setOpen(false);
              }}
            >
              Apply range
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
