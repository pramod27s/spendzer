import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: React.ReactNode;
  hint?: React.ReactNode;
  disabled?: boolean;
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Select…",
  className,
  id,
  size = "md",
  "aria-label": ariaLabel,
}: {
  value: string | undefined;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  id?: string;
  size?: "sm" | "md";
  "aria-label"?: string;
}) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger
        id={id}
        aria-label={ariaLabel}
        className={cn(
          "inline-flex w-full items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 text-left text-sm shadow-[var(--shadow-card)] transition-[border-color,box-shadow] hover:border-border-strong focus-visible:border-brand focus-visible:shadow-[0_0_0_3px_var(--ring)] focus-visible:outline-none data-[placeholder]:text-text-3",
          size === "sm" ? "h-8 text-[13px]" : "h-10",
          className,
        )}
      >
        <span className="truncate">
          <SelectPrimitive.Value placeholder={placeholder} />
        </span>
        <SelectPrimitive.Icon>
          <ChevronDown className="size-4 text-text-3" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={6}
          className="z-50 max-h-[min(22rem,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow-pop)] data-[state=open]:animate-fade-in"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((opt) => (
              <SelectPrimitive.Item
                key={opt.value}
                value={opt.value}
                disabled={opt.disabled}
                className="relative flex cursor-default select-none items-center gap-2 rounded-lg py-2 pl-2.5 pr-8 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-surface-2"
              >
                <SelectPrimitive.ItemText>{opt.label}</SelectPrimitive.ItemText>
                {opt.hint && <span className="ml-auto text-xs text-text-3">{opt.hint}</span>}
                <SelectPrimitive.ItemIndicator className="absolute right-2.5">
                  <Check className="size-4 text-brand" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

/** Pill-style segmented control for small option sets (periods, modes). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  size = "md",
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: React.ReactNode }[];
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <div
      role="radiogroup"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-xl border border-border bg-surface-2 p-0.5",
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "whitespace-nowrap rounded-[10px] font-medium transition-all",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-[13px]",
              active
                ? "bg-surface text-text shadow-[var(--shadow-card)] ring-1 ring-border"
                : "text-text-3 hover:text-text",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
