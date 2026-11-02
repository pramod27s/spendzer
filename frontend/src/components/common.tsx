import { ArrowDownRight, ArrowUpRight, CloudUpload, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import type { Category } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, Skeleton } from "@/components/ui/primitives";
import { categoryColor } from "@/lib/colors";
import { formatINR, type MoneyLike } from "@/lib/format";
import { categoryIcon } from "@/lib/icons";
import { cn } from "@/lib/utils";

/* ---------- Money ---------- */

export function Amount({
  value,
  direction,
  paise = true,
  className,
}: {
  value: MoneyLike;
  direction?: "debit" | "credit";
  paise?: boolean;
  className?: string;
}) {
  const credit = direction === "credit";
  return (
    <span className={cn("tabular whitespace-nowrap font-medium", credit && "text-good-ink", className)}>
      {credit ? "+" : direction === "debit" ? "−" : ""}
      {formatINR(value, { paise })}
    </span>
  );
}

/* ---------- Category chip ---------- */

export function CategoryDot({ category, size = "md" }: { category?: Pick<Category, "icon" | "color"> | null; size?: "sm" | "md" | "lg" }) {
  const Icon = categoryIcon(category?.icon);
  const color = categoryColor(category?.color);
  const dims = { sm: "size-6 rounded-md [&_svg]:size-3.5", md: "size-8 rounded-lg [&_svg]:size-4", lg: "size-10 rounded-xl [&_svg]:size-5" }[size];
  return (
    <span
      className={cn("relative grid shrink-0 place-items-center", dims)}
      style={{ color }}
      aria-hidden
    >
      <span className="absolute inset-0 rounded-[inherit] opacity-[0.14]" style={{ background: color }} />
      <Icon className="relative" />
    </span>
  );
}

export function CategoryLabel({ category, fallback = "Uncategorized" }: { category?: Category | null; fallback?: string }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2">
      <CategoryDot category={category} size="sm" />
      <span className="truncate text-[13px] text-text-2">{category?.name ?? fallback}</span>
    </span>
  );
}

/* ---------- Merchant avatar ---------- */

export function MerchantAvatar({ name, category }: { name: string; category?: Category | null }) {
  const letter = (name.trim()[0] ?? "?").toUpperCase();
  if (category) return <CategoryDot category={category} />;
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-xs font-semibold text-text-2">
      {letter}
    </span>
  );
}

/* ---------- KPI card ---------- */

export function KpiCard({
  label,
  value,
  icon: Icon,
  delta,
  deltaGoodWhen = "up",
  footnote,
  loading,
  tone,
  className,
}: {
  label: string;
  value: React.ReactNode;
  icon?: LucideIcon;
  delta?: number | null;
  deltaGoodWhen?: "up" | "down";
  footnote?: React.ReactNode;
  loading?: boolean;
  tone?: "critical";
  className?: string;
}) {
  const hasDelta = delta !== null && delta !== undefined && Number.isFinite(delta);
  const up = hasDelta && delta! > 0;
  const good = hasDelta && (deltaGoodWhen === "up" ? delta! >= 0 : delta! <= 0);
  const DeltaIcon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <Card className={cn("relative overflow-hidden p-5", className)}>
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-text-2">{label}</p>
        {Icon && <Icon className="size-4 text-text-3" aria-hidden />}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-32" />
      ) : (
        <p
          className={cn(
            "mt-2 text-[28px] font-semibold leading-none tracking-[-0.03em]",
            tone === "critical" && "text-critical-ink",
          )}
        >
          {value}
        </p>
      )}
      <div className="mt-3 flex min-h-5 items-center gap-2 text-xs text-text-3">
        {hasDelta && !loading && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-medium",
              good ? "bg-good-soft text-good-ink" : "bg-critical-soft text-critical-ink",
            )}
          >
            <DeltaIcon className="size-3" aria-hidden />
            {Math.abs(delta!).toFixed(Math.abs(delta!) >= 10 ? 0 : 1)}%
            <span className="sr-only">{up ? "up" : "down"}</span>
          </span>
        )}
        {footnote}
      </div>
    </Card>
  );
}

/* ---------- Empty state ---------- */

export function EmptyState({
  icon: Icon = CloudUpload,
  title,
  description,
  action,
  compact,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "py-8" : "py-14", className)}>
      <div className="relative mb-4">
        <div className="absolute inset-0 -m-3 rounded-full bg-brand-soft blur-xl" aria-hidden />
        <div className="relative grid size-12 place-items-center rounded-2xl border border-border bg-surface shadow-[var(--shadow-card)]">
          <Icon className="size-5 text-brand" />
        </div>
      </div>
      <p className="text-[15px] font-semibold">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm leading-relaxed text-text-2">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function UploadCta({ label = "Upload a statement" }: { label?: string }) {
  return (
    <Button asChild variant="brand">
      <Link to="/upload">
        <CloudUpload /> {label}
      </Link>
    </Button>
  );
}
