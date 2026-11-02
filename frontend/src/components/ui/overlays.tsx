import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/* ---------------- Dialog ---------------- */

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  title,
  description,
  children,
  className,
  wide,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  wide?: boolean;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-[var(--shadow-lift)] focus:outline-none data-[state=open]:animate-fade-up",
          wide ? "max-w-2xl" : "max-w-md",
          className,
        )}
      >
        <div className="mb-5 pr-8">
          <DialogPrimitive.Title className="text-lg font-semibold tracking-tight">{title}</DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-1 text-sm text-text-2">
              {description}
            </DialogPrimitive.Description>
          ) : (
            <DialogPrimitive.Description className="sr-only">{String(title)}</DialogPrimitive.Description>
          )}
        </div>
        {children}
        <DialogPrimitive.Close
          className="absolute right-4 top-4 rounded-md p-1.5 text-text-3 transition-colors hover:bg-surface-2 hover:text-text"
          aria-label="Close"
        >
          <X className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

/* ---------------- Popover ---------------- */

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = "start", sideOffset = 6, ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 rounded-xl border border-border bg-surface p-1 shadow-[var(--shadow-pop)] outline-none data-[state=open]:animate-fade-in",
        className,
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
PopoverContent.displayName = "PopoverContent";

/* ---------------- Dropdown menu ---------------- */

export const DropdownMenu = DropdownPrimitive.Root;
export const DropdownMenuTrigger = DropdownPrimitive.Trigger;

export function DropdownMenuContent({
  className,
  align = "end",
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownPrimitive.Content>) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        align={align}
        sideOffset={6}
        className={cn(
          "z-50 min-w-44 rounded-xl border border-border bg-surface p-1 shadow-[var(--shadow-pop)] data-[state=open]:animate-fade-in",
          className,
        )}
        {...props}
      />
    </DropdownPrimitive.Portal>
  );
}

export function DropdownMenuItem({
  className,
  destructive,
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownPrimitive.Item> & { destructive?: boolean }) {
  return (
    <DropdownPrimitive.Item
      className={cn(
        "flex cursor-default select-none items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors data-[highlighted]:bg-surface-2 [&_svg]:size-4 [&_svg]:text-text-3",
        destructive && "text-critical-ink [&_svg]:text-critical-ink",
        className,
      )}
      {...props}
    />
  );
}

export const DropdownMenuSeparator = () => (
  <DropdownPrimitive.Separator className="-mx-1 my-1 h-px bg-border" />
);

export const DropdownMenuLabel = ({ children }: { children: React.ReactNode }) => (
  <DropdownPrimitive.Label className="px-2.5 py-1.5 text-xs text-text-3">{children}</DropdownPrimitive.Label>
);

/* ---------------- Tooltip ---------------- */

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <TooltipPrimitive.Root delayDuration={150}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-64 rounded-lg bg-primary px-2.5 py-1.5 text-xs leading-relaxed text-primary-fg shadow-[var(--shadow-pop)] data-[state=delayed-open]:animate-fade-in"
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
