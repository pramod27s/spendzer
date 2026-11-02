import {
  ArrowRight,
  CircleAlert,
  CircleCheck,
  CloudUpload,
  Ellipsis,
  FileSpreadsheet,
  LoaderCircle,
  Lock,
  LockOpen,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useAccounts, useCreateUpload, useDeleteUpload, useSources, useSubmitMapping, useUpload, useUploads } from "@/api/queries";
import type { Upload, UploadStatus } from "@/api/types";
import { AccountDialog, accountIcon } from "@/components/AccountDialog";
import { PageHeader } from "@/components/AppShell";
import { ColumnMapper } from "@/components/ColumnMapper";
import { EmptyState } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/overlays";
import { Badge, Card, CardHeader, Field, Input, Skeleton } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { formatDay } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAX_BYTES = 10 * 1024 * 1024;

export function UploadDropzone({
  onFile,
  disabled,
  extensions,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
  extensions: string[];
}) {
  const formats = extensions.map((e) => e.slice(1).toUpperCase()).join(", ");
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function pick(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    if (file.size > MAX_BYTES) {
      toast.error("Statements must be 10 MB or smaller.");
      return;
    }
    if (!extensions.some((ext) => file.name.toLowerCase().endsWith(ext))) {
      toast.error(`This statement type takes ${formats} files.`);
      return;
    }
    onFile(file);
  }

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!disabled) pick(e.dataTransfer.files);
      }}
      className={cn(
        "group relative flex w-full flex-col items-center justify-center overflow-hidden rounded-2xl border-[1.5px] border-dashed px-6 py-12 text-center transition-all disabled:cursor-not-allowed disabled:opacity-50",
        over ? "border-brand bg-brand-soft" : "border-border-strong bg-surface-2/40 hover:border-brand/60 hover:bg-brand-soft/40",
      )}
    >
      <div className="bg-dots absolute inset-0 opacity-40 [mask-image:radial-gradient(60%_70%_at_50%_50%,black,transparent)]" aria-hidden />
      <div className={cn("relative grid size-14 place-items-center rounded-2xl border border-border bg-surface shadow-[var(--shadow-card)] transition-transform", over ? "scale-110" : "group-hover:-translate-y-0.5")}>
        <CloudUpload className="size-6 text-brand" />
      </div>
      <p className="relative mt-4 text-[15px] font-semibold">{over ? "Drop to upload" : "Drop your statement here"}</p>
      <p className="relative mt-1 text-sm text-text-2">
        or <span className="font-medium text-brand-ink underline-offset-4 group-hover:underline">browse files</span> · {formats} up to 10 MB
      </p>
      <input ref={input} type="file" accept={extensions.join(",")} className="hidden" onChange={(e) => pick(e.target.files)} />
    </button>
  );
}

const STATUS_META: Record<UploadStatus, { label: string; tone: "neutral" | "brand" | "good" | "warning" | "critical" }> = {
  pending: { label: "Queued", tone: "neutral" },
  parsing: { label: "Reading", tone: "brand" },
  needs_mapping: { label: "Needs columns", tone: "warning" },
  done: { label: "Imported", tone: "good" },
  failed: { label: "Failed", tone: "critical" },
};

function splitError(error: string | null): { code: string; message: string } {
  if (!error) return { code: "", message: "" };
  const idx = error.indexOf(": ");
  return idx === -1 ? { code: error, message: error } : { code: error.slice(0, idx), message: error.slice(idx + 2) };
}

export function ActiveUpload({
  id,
  onReset,
  onUnlock,
}: {
  id: string;
  onReset: () => void;
  onUnlock?: (password: string) => Promise<void>;
}) {
  const { data: upload } = useUpload(id);
  const submit = useSubmitMapping();
  const [password, setPassword] = useState("");
  const [unlocking, setUnlocking] = useState(false);

  if (!upload) {
    return <Skeleton className="h-40 w-full rounded-2xl" />;
  }
  if (upload.status === "pending" || upload.status === "parsing") {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <div className="relative grid size-14 place-items-center">
          <span className="absolute inset-0 animate-ping rounded-full bg-brand-soft" />
          <LoaderCircle className="relative size-7 animate-spin text-brand" />
        </div>
        <p className="mt-5 text-[15px] font-semibold">Reading {upload.file_name}…</p>
        <p className="mt-1 text-sm text-text-2">Cleaning narrations and sorting categories.</p>
      </div>
    );
  }
  if (upload.status === "needs_mapping" && upload.preview) {
    return (
      <ColumnMapper
        preview={upload.preview}
        submitting={submit.isPending}
        onSubmit={(mapping) =>
          submit.mutate(
            { id: upload.id, mapping },
            { onError: (err) => toast.error(errorMessage(err)) },
          )
        }
      />
    );
  }
  if (upload.status === "done") {
    return (
      <div className="flex flex-col items-center py-10 text-center">
        <div className="grid size-14 place-items-center rounded-full bg-good-soft">
          <CircleCheck className="size-7 text-good" />
        </div>
        <p className="mt-5 text-lg font-semibold tracking-tight">{upload.txn_count} transactions imported</p>
        {upload.period_start && upload.period_end && (
          <p className="mt-1 text-sm text-text-2">
            {formatDay(upload.period_start, true)} – {formatDay(upload.period_end, true)}
          </p>
        )}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button asChild>
            <Link to={upload.period_end ? `/dashboard?month=${upload.period_end.slice(0, 7)}` : "/dashboard"}>
              See where it went <ArrowRight />
            </Link>
          </Button>
          <Button variant="secondary" onClick={onReset}>
            Upload another
          </Button>
        </div>
      </div>
    );
  }
  const err = splitError(upload.error);
  if (err.code === "PDF_PASSWORD_REQUIRED" && onUnlock) {
    return (
      <form
        className="mx-auto flex max-w-sm flex-col items-center py-10 text-center"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!password) return;
          setUnlocking(true);
          try {
            await onUnlock(password);
          } finally {
            setUnlocking(false);
            setPassword("");
          }
        }}
      >
        <div className="grid size-14 place-items-center rounded-full bg-warning-soft">
          <Lock className="size-6 text-warning-ink" />
        </div>
        <p className="mt-5 text-[15px] font-semibold">This PDF is password-protected</p>
        <p className="mt-1 text-sm text-text-2">
          Banks often use your date of birth or customer ID. It's used once to open the file and never saved.
        </p>
        <Input
          type="password"
          autoFocus
          autoComplete="off"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="PDF password"
          className="mt-5"
          aria-label="PDF password"
        />
        <div className="mt-4 flex gap-2">
          <Button type="button" variant="ghost" onClick={onReset}>
            Cancel
          </Button>
          <Button type="submit" disabled={!password} loading={unlocking}>
            <LockOpen /> Unlock and import
          </Button>
        </div>
      </form>
    );
  }
  return (
    <div className="flex flex-col items-center py-10 text-center">
      <div className="grid size-14 place-items-center rounded-full bg-critical-soft">
        <CircleAlert className="size-7 text-critical" />
      </div>
      <p className="mt-5 text-[15px] font-semibold">We couldn't read that file</p>
      <p className="mt-1 max-w-md text-sm text-text-2">{err.message || "Something went wrong."}</p>
      <Button variant="secondary" className="mt-6" onClick={onReset}>
        <RefreshCw /> Try another file
      </Button>
    </div>
  );
}

export default function UploadPage() {
  const [params, setParams] = useSearchParams();
  const welcome = params.get("welcome") === "1";
  const { data: accounts, isLoading: accountsLoading } = useAccounts();
  const { data: sources } = useSources();
  const { data: uploads, isLoading: uploadsLoading } = useUploads();
  const create = useCreateUpload();
  const remove = useDeleteUpload();

  const statementAccounts = (accounts ?? []).filter((a) => a.type !== "cash");
  const [accountId, setAccountId] = useState<string>("");
  const [sourceType, setSourceType] = useState("generic_csv");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<Upload | null>(null);
  const [pdfPassword, setPdfPassword] = useState("");
  // The last file picked, kept in memory only so a locked PDF can be retried with its password.
  const [lastFile, setLastFile] = useState<File | null>(null);

  const source = sources?.find((s) => s.source_type === sourceType);
  const extensions = source?.extensions ?? [".csv", ".xls", ".xlsx"];

  useEffect(() => {
    if (!accountId && statementAccounts.length) setAccountId(statementAccounts[0].id);
  }, [accountId, statementAccounts]);

  // Suggest a statement type that fits the account: UPI apps for UPI accounts, and so on.
  useEffect(() => {
    const account = statementAccounts.find((a) => a.id === accountId);
    if (!account || !sources) return;
    const current = sources.find((s) => s.source_type === sourceType);
    const fits = (group: string) => (account.type === "upi" ? group === "upi" : account.type === "card" ? group !== "upi" : group === "bank");
    if (current && fits(current.group)) return;
    const next = account.type === "bank" ? "generic_csv" : sources.find((s) => fits(s.group))?.source_type;
    if (next) setSourceType(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, sources]);

  // Resume an upload that's waiting for columns.
  useEffect(() => {
    if (activeId || !uploads) return;
    const waiting = uploads.items.find((u) => u.status === "needs_mapping");
    if (waiting) setActiveId(waiting.id);
  }, [uploads, activeId]);

  async function onFile(file: File) {
    if (!accountId) {
      toast.error("Add the account this statement is from first.");
      setAccountOpen(true);
      return;
    }
    setLastFile(file);
    try {
      const upload = await create.mutateAsync({
        file,
        account_id: accountId,
        source_type: sourceType,
        pdf_password: source?.accepts_password && pdfPassword ? pdfPassword : undefined,
      });
      setActiveId(upload.id);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setPdfPassword("");
    }
  }

  async function unlock(password: string) {
    if (!lastFile) {
      toast.error("Pick the file again to unlock it.");
      setActiveId(null);
      return;
    }
    try {
      const upload = await create.mutateAsync({
        file: lastFile,
        account_id: accountId,
        source_type: sourceType,
        pdf_password: password,
      });
      setActiveId(upload.id);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const groupLabel = { bank: "Bank", card: "Credit card", upi: "UPI app" } as const;

  const accountName = (id: string) => accounts?.find((a) => a.id === id)?.name ?? "Account";

  return (
    <div className="animate-fade-up">
      <PageHeader title="Upload a statement" description="Bank, card and UPI-app statements — CSV, Excel or PDF. Raw files are deleted as soon as they're read." />

      {welcome && (
        <div className="mb-5 flex items-start justify-between gap-4 rounded-2xl border border-brand/25 bg-brand-soft px-5 py-4">
          <div>
            <p className="font-semibold text-brand-ink">You're in. Let's import your first statement.</p>
            <p className="mt-0.5 text-sm text-text-2">Add the account it's from, then drop the file below.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setParams({}, { replace: true })}>
            Dismiss
          </Button>
        </div>
      )}

      <div className={cn("grid gap-5", !activeId && "lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]")}>
        <Card className="min-w-0 p-5 sm:p-6">
          {activeId ? (
            <ActiveUpload id={activeId} onReset={() => setActiveId(null)} onUnlock={unlock} />
          ) : (
            <div className="grid gap-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Account" htmlFor="u-account">
                  {accountsLoading ? (
                    <Skeleton className="h-10" />
                  ) : statementAccounts.length ? (
                    <div className="flex gap-2">
                      <Select
                        id="u-account"
                        value={accountId}
                        onValueChange={setAccountId}
                        options={statementAccounts.map((a) => ({
                          value: a.id,
                          label: a.last4 ? `${a.name} ••${a.last4}` : a.name,
                        }))}
                      />
                      <Button variant="secondary" size="icon" onClick={() => setAccountOpen(true)} aria-label="Add account">
                        <Plus />
                      </Button>
                    </div>
                  ) : (
                    <Button variant="secondary" className="h-10 justify-start" onClick={() => setAccountOpen(true)}>
                      <Plus /> Add your first account
                    </Button>
                  )}
                </Field>
                <Field label="Statement type" htmlFor="u-source">
                  <Select
                    id="u-source"
                    value={sourceType}
                    onValueChange={setSourceType}
                    options={(sources ?? []).map((s) => ({
                      value: s.source_type,
                      label: s.label,
                      hint: groupLabel[s.group],
                    }))}
                  />
                </Field>
              </div>
              {source?.accepts_password && (
                <Field label="PDF password" htmlFor="u-pdf-password" hint="Only if the PDF is locked. Used once to open it — never stored.">
                  <Input
                    id="u-pdf-password"
                    type="password"
                    autoComplete="off"
                    value={pdfPassword}
                    onChange={(e) => setPdfPassword(e.target.value)}
                    placeholder="Leave empty if it opens without one"
                  />
                </Field>
              )}
              <UploadDropzone onFile={onFile} disabled={create.isPending} extensions={extensions} />
              <p className="flex items-center gap-2 text-xs text-text-3">
                <Lock className="size-3.5" /> Parsed in memory. Card numbers are masked to the last 4 digits before anything is saved.
              </p>
            </div>
          )}
        </Card>

        <Card className={cn("h-fit", activeId && "hidden")}>
          <CardHeader title="Where to find your statement" />
          <ol className="grid gap-3 p-5 text-sm text-text-2">
            {[
              "Open net banking or your bank's app.",
              "Go to Accounts → Statement / Account activity.",
              "Pick a date range (a full month works best).",
              "Download as Excel / CSV, or the PDF statement (HDFC, SBI, ICICI, GPay, PhonePe).",
            ].map((step, i) => (
              <li key={step} className="flex gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-semibold text-text">{i + 1}</span>
                <span className="pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
          <div className="mx-5 mb-5 rounded-xl bg-surface-2/70 px-4 py-3 text-xs leading-relaxed text-text-2">
            Upload your bank statement and your UPI-app statement for the same month — payments that show
            up in both are matched (by UPI reference, or amount, date and payee) and counted once.
          </div>
        </Card>
      </div>

      <Card className="mt-5">
        <CardHeader title="Upload history" description="Delete an upload to remove every transaction it brought in." />
        <div className="p-2 pt-3">
          {uploadsLoading ? (
            <div className="grid gap-2 p-3">
              {[0, 1].map((i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : !uploads?.items.length ? (
            <EmptyState compact icon={FileSpreadsheet} title="No uploads yet" description="Your imported statements will appear here." />
          ) : (
            <ul>
              {uploads.items.map((u) => {
                const meta = STATUS_META[u.status];
                const account = accounts?.find((a) => a.id === u.account_id);
                const Icon = account ? accountIcon(account.type) : FileSpreadsheet;
                return (
                  <li key={u.id} className="flex items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-surface-2/60">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-2 text-text-2">
                      <Icon className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{u.file_name}</p>
                      <p className="truncate text-xs text-text-3">
                        {accountName(u.account_id)}
                        {u.period_start && u.period_end && ` · ${formatDay(u.period_start)} – ${formatDay(u.period_end, true)}`}
                        {u.status === "done" && ` · ${u.txn_count} transactions`}
                        {u.status === "failed" && ` · ${splitError(u.error).message}`}
                      </p>
                    </div>
                    <Badge tone={meta.tone} className="hidden sm:inline-flex">
                      {meta.label}
                    </Badge>
                    {u.status === "needs_mapping" && u.id !== activeId && (
                      <Button size="sm" variant="secondary" onClick={() => setActiveId(u.id)}>
                        Map columns
                      </Button>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${u.file_name}`}>
                          <Ellipsis />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem destructive onSelect={() => setConfirmDelete(u)}>
                          <Trash2 /> Delete upload
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </Card>

      <AccountDialog open={accountOpen} onOpenChange={setAccountOpen} onCreated={(a) => setAccountId(a.id)} />

      <Dialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <DialogContent
          title="Delete this upload?"
          description={
            confirmDelete?.status === "done"
              ? `This removes ${confirmDelete.txn_count} transactions imported from ${confirmDelete.file_name}. It can't be undone.`
              : "This removes the upload from your history."
          }
        >
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={async () => {
                if (!confirmDelete) return;
                try {
                  await remove.mutateAsync(confirmDelete.id);
                  if (activeId === confirmDelete.id) setActiveId(null);
                  toast.success("Upload deleted");
                  setConfirmDelete(null);
                } catch (err) {
                  toast.error(errorMessage(err));
                }
              }}
            >
              Delete upload
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
