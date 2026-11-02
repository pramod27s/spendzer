import { useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useAccounts, useCreateTransaction } from "@/api/queries";
import { CategoryPicker } from "@/components/CategoryPicker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { Field, Input } from "@/components/ui/primitives";
import { Segmented, Select } from "@/components/ui/select";
import { formatINR, toISODate } from "@/lib/format";

export function MoneyInput({
  value,
  onChange,
  id,
  invalid,
}: {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  invalid?: boolean;
}) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3 grid place-items-center text-[15px] text-text-3">₹</span>
      <Input
        id={id}
        inputMode="decimal"
        autoComplete="off"
        value={value}
        aria-invalid={invalid}
        onChange={(e) => {
          const next = e.target.value.replace(/[^\d.]/g, "");
          if (/^\d{0,10}(\.\d{0,2})?$/.test(next)) onChange(next);
        }}
        placeholder="0"
        className="tabular pl-7 text-[15px] font-medium"
      />
    </div>
  );
}

export function ManualEntryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data: accounts = [] } = useAccounts();
  const create = useCreateTransaction();
  const [direction, setDirection] = useState<"debit" | "credit">("debit");
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [date, setDate] = useState(() => toISODate(new Date()));
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string>("");
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);

  const cash = accounts.find((a) => a.type === "cash");
  const amountOk = Number(amount) > 0;
  const merchantOk = merchant.trim().length > 0;

  function reset() {
    setAmount("");
    setMerchant("");
    setNote("");
    setCategoryId(null);
    setTouched(false);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!amountOk || !merchantOk) return;
    try {
      const txn = await create.mutateAsync({
        txn_date: date,
        amount,
        direction,
        merchant: merchant.trim(),
        category_id: categoryId ?? undefined,
        account_id: accountId || cash?.id || undefined,
        note: note.trim() || undefined,
      });
      toast.success(`${direction === "debit" ? "Spend" : "Income"} of ${formatINR(txn.amount)} added`);
      reset();
      onOpenChange(false);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Add a cash entry" description="For money that never touched a statement.">
        <form onSubmit={submit} className="grid gap-4">
          <Segmented
            value={direction}
            onChange={setDirection}
            options={[
              { value: "debit", label: "Money out" },
              { value: "credit", label: "Money in" },
            ]}
            className="w-full [&>button]:flex-1"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Amount" htmlFor="me-amount" error={touched && !amountOk ? "Enter an amount" : null}>
              <MoneyInput id="me-amount" value={amount} onChange={setAmount} invalid={touched && !amountOk} />
            </Field>
            <Field label="Date" htmlFor="me-date">
              <Input id="me-date" type="date" value={date} max={toISODate(new Date())} onChange={(e) => setDate(e.target.value)} />
            </Field>
          </div>
          <Field
            label={direction === "debit" ? "Paid to" : "Received from"}
            htmlFor="me-merchant"
            error={touched && !merchantOk ? "Who was it?" : null}
          >
            <Input
              id="me-merchant"
              value={merchant}
              maxLength={160}
              onChange={(e) => setMerchant(e.target.value)}
              placeholder={direction === "debit" ? "e.g. Chai stall, auto fare" : "e.g. Pocket money, tutoring"}
              aria-invalid={touched && !merchantOk}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Category" htmlFor="me-category" hint="Leave empty to auto-detect">
              <CategoryPicker id="me-category" value={categoryId} onChange={(c) => setCategoryId(c?.id ?? null)} direction={direction} />
            </Field>
            <Field label="Account" htmlFor="me-account">
              <Select
                id="me-account"
                value={accountId || cash?.id}
                onValueChange={setAccountId}
                placeholder="Cash"
                options={accounts.map((a) => ({ value: a.id, label: a.name }))}
              />
            </Field>
          </div>
          <Field label="Note" htmlFor="me-note">
            <Input id="me-note" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} placeholder="Optional" />
          </Field>
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending}>
              Add entry
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
