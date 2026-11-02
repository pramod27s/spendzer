import {
  Bell,
  CheckCheck,
  CircleAlert,
  CloudUpload,
  Gauge,
  Repeat,
  Sparkles,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAlerts, useMarkAlertRead, useMarkAllAlertsRead } from "@/api/queries";
import type { Alert, AlertType } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { cn } from "@/lib/utils";

const META: Record<AlertType, { icon: typeof Bell; tone: string; to: (a: Alert) => string }> = {
  budget_80: { icon: TriangleAlert, tone: "bg-warning-soft text-warning-ink", to: (a) => `/plan/${a.month.slice(0, 7)}` },
  budget_100: { icon: CircleAlert, tone: "bg-critical-soft text-critical-ink", to: (a) => `/plan/${a.month.slice(0, 7)}` },
  pace: { icon: Gauge, tone: "bg-warning-soft text-warning-ink", to: (a) => `/plan/${a.month.slice(0, 7)}` },
  anomaly: {
    icon: Sparkles,
    tone: "bg-brand-soft text-brand-ink",
    to: (a) => `/transactions${a.category_id ? `?category_id=${a.category_id}` : ""}`,
  },
  recurring_change: { icon: Repeat, tone: "bg-brand-soft text-brand-ink", to: () => "/recurring" },
  income_missing: { icon: Wallet, tone: "bg-warning-soft text-warning-ink", to: () => "/transactions?kind=income" },
  stale_data: { icon: CloudUpload, tone: "bg-surface-2 text-text-2", to: () => "/upload" },
};

function timeAgo(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function AlertBell({ className }: { className?: string }) {
  const { data } = useAlerts();
  const markRead = useMarkAlertRead();
  const markAll = useMarkAllAlertsRead();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const unread = data?.unread ?? 0;
  const alerts = data?.alerts ?? [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          "relative grid size-9 place-items-center rounded-lg text-text-2 transition-colors hover:bg-surface-2 hover:text-text",
          className,
        )}
        aria-label={unread ? `Alerts, ${unread} unread` : "Alerts"}
      >
        <Bell className="size-[18px]" />
        {unread > 0 && (
          <span className="tabular absolute -right-0.5 -top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-critical px-1 text-[10.5px] font-semibold text-white ring-2 ring-[var(--background)]">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(380px,calc(100vw-2rem))] p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm font-semibold">Alerts</p>
          {unread > 0 && (
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => markAll.mutate()}>
              <CheckCheck /> Mark all read
            </Button>
          )}
        </div>
        <ul className="max-h-[420px] overflow-y-auto p-1">
          {alerts.length === 0 && (
            <li className="px-4 py-10 text-center text-sm text-text-3">
              Nothing to flag. We'll tell you when a budget gets close.
            </li>
          )}
          {alerts.map((a) => {
            const meta = META[a.type] ?? META.anomaly;
            return (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => {
                    if (!a.read) markRead.mutate(a.id);
                    setOpen(false);
                    navigate(meta.to(a));
                  }}
                  className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-surface-2"
                >
                  <span className={cn("mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg", meta.tone)}>
                    <meta.icon className="size-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className={cn("block text-[13.5px] leading-snug", a.read ? "text-text-2" : "font-medium text-text")}>
                      {a.message}
                    </span>
                    <span className="mt-0.5 block text-[11.5px] text-text-3">{timeAgo(a.created_at)}</span>
                  </span>
                  {!a.read && <span className="mt-2 size-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
