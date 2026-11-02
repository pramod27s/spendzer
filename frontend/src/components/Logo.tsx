import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--brand)" />
      <path
        d="M10 20.5c1.2 1.6 3.3 2.5 6 2.5 3.6 0 6-1.7 6-4.3 0-2.4-1.9-3.4-5.6-4.1-2.6-.5-3.4-.9-3.4-1.8 0-.9 1-1.5 2.7-1.5 1.6 0 2.8.6 3.6 1.6"
        fill="none"
        stroke="var(--brand-fg)"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-[17px] font-semibold tracking-[-0.02em]">Spendzer</span>
    </span>
  );
}
