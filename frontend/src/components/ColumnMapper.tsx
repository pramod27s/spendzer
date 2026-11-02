import { ArrowRight, Columns3 } from "lucide-react";
import { useMemo, useState } from "react";

import type { ColumnMapping, UploadPreview } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge, Field } from "@/components/ui/primitives";
import { Segmented, Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

type Mode = ColumnMapping["amount_mode"];
type Role = "date_col" | "description_col" | "debit_col" | "credit_col" | "amount_col" | "type_col";

const ROLE_LABEL: Record<Role, string> = {
  date_col: "Date",
  description_col: "Description",
  debit_col: "Money out",
  credit_col: "Money in",
  amount_col: "Amount",
  type_col: "Dr / Cr",
};

const MODE_ROLES: Record<Mode, Role[]> = {
  split: ["debit_col", "credit_col"],
  signed: ["amount_col"],
  type: ["amount_col", "type_col"],
};

export function ColumnMapper({
  preview,
  onSubmit,
  submitting,
}: {
  preview: UploadPreview;
  onSubmit: (mapping: ColumnMapping) => void;
  submitting?: boolean;
}) {
  const s = preview.suggested_mapping;
  const [mode, setMode] = useState<Mode>(s.amount_mode);
  const [cols, setCols] = useState<Record<Role, string | undefined>>({
    date_col: s.date_col ?? undefined,
    description_col: s.description_col ?? undefined,
    debit_col: s.debit_col ?? undefined,
    credit_col: s.credit_col ?? undefined,
    amount_col: s.amount_col ?? undefined,
    type_col: s.type_col ?? undefined,
  });

  const activeRoles: Role[] = ["date_col", "description_col", ...MODE_ROLES[mode]];
  const missing = activeRoles.filter((r) => !cols[r]);
  const roleByColumn = useMemo(() => {
    const m = new Map<string, Role>();
    for (const r of activeRoles) if (cols[r]) m.set(cols[r]!, r);
    return m;
  }, [cols, activeRoles]);

  const options = preview.columns.map((c) => ({ value: c, label: c }));
  const set = (role: Role) => (value: string) => setCols((prev) => ({ ...prev, [role]: value }));

  function submit() {
    if (missing.length) return;
    const mapping: ColumnMapping = {
      date_col: cols.date_col!,
      description_col: cols.description_col!,
      amount_mode: mode,
    };
    for (const r of MODE_ROLES[mode]) Object.assign(mapping, { [r]: cols[r] ?? null });
    onSubmit(mapping);
  }

  return (
    <div className="grid min-w-0 gap-6 [&>*]:min-w-0">
      <div className="flex items-start gap-3 rounded-xl bg-brand-soft px-4 py-3 text-sm text-brand-ink">
        <Columns3 className="mt-0.5 size-4 shrink-0" />
        <p>
          First upload for this account — tell us which column is which. We've guessed from the headers;
          we'll remember it next time.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Date column" htmlFor="m-date">
          <Select id="m-date" value={cols.date_col} onValueChange={set("date_col")} options={options} />
        </Field>
        <Field label="Description column" htmlFor="m-desc">
          <Select id="m-desc" value={cols.description_col} onValueChange={set("description_col")} options={options} />
        </Field>
      </div>

      <div className="grid gap-3">
        <p className="text-[13px] font-medium text-text-2">How are amounts shown?</p>
        <Segmented
          value={mode}
          onChange={setMode}
          options={[
            { value: "split", label: "Separate in / out columns" },
            { value: "signed", label: "One ± amount column" },
            { value: "type", label: "Amount + Dr/Cr column" },
          ]}
          className="w-full overflow-x-auto scrollbar-none [&>button]:flex-1"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          {MODE_ROLES[mode].map((role) => (
            <Field
              key={role}
              label={`${ROLE_LABEL[role]} column`}
              htmlFor={`m-${role}`}
              hint={role === "amount_col" && mode === "signed" ? "Negative numbers or a “Dr” suffix count as money out." : undefined}
            >
              <Select id={`m-${role}`} value={cols[role]} onValueChange={set(role)} options={options} />
            </Field>
          ))}
        </div>
      </div>

      <div>
        <p className="mb-2 text-[13px] font-medium text-text-2">Preview</p>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[560px] text-left text-[12.5px]">
            <thead className="bg-surface-2/70">
              <tr>
                {preview.columns.map((c) => {
                  const role = roleByColumn.get(c);
                  return (
                    <th key={c} className={cn("whitespace-nowrap px-3 py-2 align-bottom font-medium", role ? "text-text" : "text-text-3")}>
                      {role && (
                        <Badge tone="brand" className="mb-1 block w-fit">
                          {ROLE_LABEL[role]}
                        </Badge>
                      )}
                      {c}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {preview.sample_rows.map((row, i) => (
                <tr key={i} className="border-t border-border">
                  {preview.columns.map((c, j) => (
                    <td
                      key={c}
                      className={cn(
                        "max-w-64 truncate whitespace-nowrap px-3 py-2",
                        roleByColumn.has(c) ? "text-text" : "text-text-3",
                        roleByColumn.get(c) === "description_col" && "font-mono text-[11.5px]",
                      )}
                    >
                      {row[j] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex flex-col-reverse items-stretch justify-between gap-3 sm:flex-row sm:items-center">
        <p className="text-xs text-text-3">
          {missing.length ? `Still needed: ${missing.map((r) => ROLE_LABEL[r]).join(", ")}` : "Looks good. We'll parse every row now."}
        </p>
        <Button onClick={submit} disabled={missing.length > 0} loading={submitting}>
          Import transactions <ArrowRight />
        </Button>
      </div>
    </div>
  );
}
