import * as LabelPrimitive from "@radix-ui/react-label";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-2xl border border-border bg-surface shadow-[var(--shadow-card)]",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)}>
      <div className="min-w-0">
        <h3 className="text-[15px] font-semibold tracking-tight text-text">{title}</h3>
        {description && <p className="mt-0.5 text-[13px] text-text-3">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-text shadow-[var(--shadow-card)] transition-[border-color,box-shadow] placeholder:text-text-3 hover:border-border-strong focus-visible:border-brand focus-visible:shadow-[0_0_0_3px_var(--ring)] focus-visible:outline-none disabled:opacity-50 aria-[invalid=true]:border-critical",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-[13px] font-medium text-text-2", className)}
    {...props}
  />
));
Label.displayName = "Label";

export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  error?: string | null;
  hint?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? (
        <p className="text-[12.5px] text-critical-ink" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-[12.5px] text-text-3">{hint}</p>
      ) : null}
    </div>
  );
}

type BadgeTone = "neutral" | "brand" | "good" | "warning" | "critical" | "outline";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-text-2",
  brand: "bg-brand-soft text-brand-ink",
  good: "bg-good-soft text-good-ink",
  warning: "bg-warning-soft text-warning-ink",
  critical: "bg-critical-soft text-critical-ink",
  outline: "border border-border text-text-2",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11.5px] font-medium [&_svg]:size-3",
        BADGE_TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} aria-hidden />;
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-text-3">
      {children}
    </kbd>
  );
}

export function Separator({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-border", className)} role="separator" />;
}
