import { Building2, CreditCard, Smartphone, Wallet } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useCreateAccount } from "@/api/queries";
import type { Account, AccountType } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { Field, Input } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export const ACCOUNT_TYPES: { value: AccountType; label: string; icon: typeof Building2 }[] = [
  { value: "bank", label: "Bank", icon: Building2 },
  { value: "card", label: "Credit card", icon: CreditCard },
  { value: "upi", label: "UPI app", icon: Smartphone },
  { value: "cash", label: "Cash", icon: Wallet },
];

export function accountIcon(type: AccountType) {
  return ACCOUNT_TYPES.find((t) => t.value === type)?.icon ?? Building2;
}

/** The add-account form, used in the dialog and in onboarding. */
export function AccountForm({
  onCreated,
  onCancel,
  submitLabel = "Add account",
  autoFocus = true,
}: {
  onCreated?: (account: Account) => void;
  onCancel?: () => void;
  submitLabel?: string;
  autoFocus?: boolean;
}) {
  const create = useCreateAccount();
  const [type, setType] = useState<AccountType>("bank");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [last4, setLast4] = useState("");
  const [touched, setTouched] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!name.trim()) return;
    try {
      const account = await create.mutateAsync({
        name: name.trim(),
        type,
        institution: institution.trim() || undefined,
        last4: last4.trim() || undefined,
      });
      toast.success(`${account.name} added`);
      setName("");
      setInstitution("");
      setLast4("");
      setTouched(false);
      onCreated?.(account);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Account type">
        {ACCOUNT_TYPES.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={type === value}
            onClick={() => setType(value)}
            className={cn(
              "flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-xs font-medium transition-all",
              type === value
                ? "border-brand bg-brand-soft text-brand-ink shadow-[0_0_0_3px_var(--ring)]"
                : "border-border text-text-2 hover:border-border-strong",
            )}
          >
            <Icon className="size-5" />
            {label}
          </button>
        ))}
      </div>
      <Field label="Account name" htmlFor="acc-name" error={touched && !name.trim() ? "Give it a name" : null}>
        <Input
          id="acc-name"
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          placeholder={type === "card" ? "e.g. Travel card" : type === "upi" ? "e.g. Google Pay" : "e.g. Salary account"}
          aria-invalid={touched && !name.trim()}
          autoFocus={autoFocus}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Bank or provider" htmlFor="acc-inst">
          <Input id="acc-inst" value={institution} maxLength={120} onChange={(e) => setInstitution(e.target.value)} placeholder="Optional" />
        </Field>
        <Field label="Last 4 digits" htmlFor="acc-last4" hint="Helps spot transfers between your own accounts.">
          <Input
            id="acc-last4"
            inputMode="numeric"
            value={last4}
            maxLength={4}
            onChange={(e) => setLast4(e.target.value.replace(/\D/g, ""))}
            placeholder="1234"
            className="tabular"
          />
        </Field>
      </div>
      <div className="mt-2 flex justify-end gap-2">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={create.isPending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

export function AccountDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (account: Account) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Add an account" description="The bank, card or UPI app your statements come from.">
        <AccountForm
          onCancel={() => onOpenChange(false)}
          onCreated={(account) => {
            onCreated?.(account);
            onOpenChange(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
