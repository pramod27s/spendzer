import { Check, Repeat, RotateCcw, X } from "lucide-react";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useRecurring, useUpdateRecurring } from "@/api/queries";
import type { RecurringGroup, RecurringStatus } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { EmptyState, MerchantAvatar, UploadCta } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, Skeleton } from "@/components/ui/primitives";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { formatDay, formatINR } from "@/lib/format";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function rhythm(g: RecurringGroup): string {
  if (g.frequency === "weekly") return `Every ${WEEKDAYS[g.typical_day] ?? "week"}`;
  if (g.frequency === "yearly") return "Every year";
  return `Monthly, around the ${ordinal(g.typical_day)}`;
}

function Row({ group }: { group: RecurringGroup }) {
  const categories = useCategoryMap();
  const update = useUpdateRecurring();
  const cat = group.category_id ? categories.get(group.category_id) : null;
  const dismissed = group.status === "dismissed";

  const set = (status: RecurringStatus, message: string) =>
    update.mutate(
      { id: group.id, status },
      { onSuccess: () => toast.success(message), onError: (err) => toast.error(errorMessage(err)) },
    );

  return (
    <li className={cn("flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center", dismissed && "opacity-60")}>
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <MerchantAvatar name={group.merchant} category={cat} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold">{group.merchant}</p>
            {group.status === "confirmed" && (
              <Badge tone="brand">
                <Check /> Confirmed
              </Badge>
            )}
            {!group.active && !dismissed && <Badge tone="warning">Seems to have stopped</Badge>}
            {dismissed && <Badge>Not recurring</Badge>}
          </div>
          <p className="truncate text-xs text-text-3">
            {cat?.name ?? "Uncategorized"} · {rhythm(group)} · seen {group.occurrences}×
            {group.last_date && ` · last ${formatDay(group.last_date, true)}`}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 sm:justify-end">
        <div className="text-right">
          <p className="tabular text-[15px] font-semibold">{formatINR(group.typical_amount)}</p>
          {group.frequency !== "monthly" && <p className="tabular text-xs text-text-3">{formatINR(group.monthly_amount)}/mo</p>}
        </div>
        <div className="flex gap-1.5">
          {dismissed ? (
            <Button size="sm" variant="secondary" onClick={() => set("detected", `${group.merchant} restored`)} loading={update.isPending}>
              <RotateCcw /> Restore
            </Button>
          ) : (
            <>
              {group.status !== "confirmed" && (
                <Button size="sm" variant="secondary" onClick={() => set("confirmed", `${group.merchant} confirmed`)} loading={update.isPending}>
                  <Check /> Confirm
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => set("dismissed", `${group.merchant} won't be treated as recurring`)}
                aria-label={`Dismiss ${group.merchant}`}
              >
                <X /> Dismiss
              </Button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}

export default function RecurringPage() {
  const { data, isLoading } = useRecurring();
  const groups = data?.groups ?? [];
  const live = groups.filter((g) => g.status !== "dismissed" && g.active);
  const others = groups.filter((g) => !live.includes(g));

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Recurring"
        description="Subscriptions, rent and EMIs Spendzer spotted in your statements. They become your plan's fixed costs."
      />
      {isLoading ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState
            icon={Repeat}
            title="No recurring charges yet"
            description="We need about three months of statements to spot a pattern. Upload more history to see them here."
            action={<UploadCta />}
          />
        </Card>
      ) : (
        <div className="grid gap-5">
          <Card className="flex flex-wrap items-end justify-between gap-4 p-5 sm:p-6">
            <div>
              <p className="text-[13px] font-medium text-text-2">Committed every month</p>
              <p className="tabular mt-1 text-[32px] font-semibold leading-none tracking-[-0.03em]">{formatINR(data?.monthly_total)}</p>
            </div>
            <p className="text-sm text-text-3">
              {live.length} active {live.length === 1 ? "charge" : "charges"}
            </p>
          </Card>
          <Card>
            <ul className="divide-y divide-border">
              {[...live, ...others].map((g) => (
                <Row key={g.id} group={g} />
              ))}
            </ul>
          </Card>
          <p className="text-center text-xs text-text-3">
            A charge counts as recurring after 3 payments to the same merchant, about a month (or a week) apart, within 10% of the usual amount.
          </p>
        </div>
      )}
    </div>
  );
}
