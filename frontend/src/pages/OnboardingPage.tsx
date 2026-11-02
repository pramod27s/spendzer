import * as SliderPrimitive from "@radix-ui/react-slider";
import { ArrowLeft, ArrowRight, Check, CloudUpload, PiggyBank, ShieldCheck, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import { useAccounts, useCreateUpload, useSources, useUpdateMe } from "@/api/queries";
import type { Account } from "@/api/types";
import { AccountForm, accountIcon } from "@/components/AccountDialog";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { formatINR } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ActiveUpload, UploadDropzone } from "@/pages/UploadPage";

const STEPS = [
  { title: "Savings goal", icon: PiggyBank },
  { title: "Account", icon: Wallet },
  { title: "Statement", icon: CloudUpload },
];

function Progress({ step }: { step: number }) {
  return (
    <ol className="flex items-center gap-2" aria-label="Setup progress">
      {STEPS.map((s, i) => (
        <li key={s.title} className="flex items-center gap-2">
          <span
            className={cn(
              "grid size-7 place-items-center rounded-full text-xs font-semibold transition-colors",
              i < step ? "bg-brand text-brand-fg" : i === step ? "bg-primary text-primary-fg" : "bg-surface-2 text-text-3",
            )}
            aria-current={i === step ? "step" : undefined}
          >
            {i < step ? <Check className="size-3.5" /> : i + 1}
          </span>
          <span className={cn("hidden whitespace-nowrap text-[13px] font-medium sm:inline", i === step ? "text-text" : "text-text-3")}>{s.title}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-border-strong sm:w-10" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

function SavingsStep({ onNext }: { onNext: () => void }) {
  const { user, setUser } = useAuth();
  const update = useUpdateMe();
  const [pct, setPct] = useState(Number(user?.monthly_savings_target_pct ?? 20));
  const example = 30000;
  return (
    <div className="grid gap-7">
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.03em]">How much do you want to save each month?</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-text-2">
          Spendzer takes this off the top of your income before budgeting anything else. You can change it any month.
        </p>
      </div>
      <div className="rounded-2xl border border-border bg-surface-2/50 p-6">
        <div className="flex items-end justify-between">
          <p className="tabular text-[56px] font-semibold leading-none tracking-[-0.04em]">{pct}%</p>
          <p className="pb-2 text-right text-sm text-text-2">
            On {formatINR(example)} a month,
            <br />
            that's <span className="font-semibold text-text">{formatINR((example * pct) / 100)}</span> saved
          </p>
        </div>
        <SliderPrimitive.Root
          value={[pct]}
          min={0}
          max={60}
          step={1}
          onValueChange={([v]) => setPct(v)}
          className="relative mt-6 flex h-5 w-full touch-none select-none items-center"
          aria-label="Monthly savings target"
        >
          <SliderPrimitive.Track className="relative h-1.5 grow overflow-hidden rounded-full bg-surface-3">
            <SliderPrimitive.Range className="absolute h-full rounded-full bg-brand" />
          </SliderPrimitive.Track>
          <SliderPrimitive.Thumb className="block size-6 rounded-full border-2 border-brand bg-surface shadow-[var(--shadow-pop)] focus-visible:shadow-[0_0_0_4px_var(--ring)] focus-visible:outline-none" />
        </SliderPrimitive.Root>
        <div className="mt-5 flex flex-wrap gap-2">
          {[
            { v: 10, label: "10% · starting out" },
            { v: 20, label: "20% · recommended" },
            { v: 30, label: "30% · ambitious" },
          ].map((p) => (
            <button
              key={p.v}
              type="button"
              onClick={() => setPct(p.v)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                pct === p.v ? "border-brand bg-brand-soft text-brand-ink" : "border-border text-text-2 hover:bg-surface-2",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex justify-end">
        <Button
          size="lg"
          loading={update.isPending}
          onClick={async () => {
            try {
              setUser(await update.mutateAsync({ monthly_savings_target_pct: String(pct) }));
              onNext();
            } catch (err) {
              toast.error(errorMessage(err));
            }
          }}
        >
          Continue <ArrowRight />
        </Button>
      </div>
    </div>
  );
}

function AccountStep({ onNext, onBack }: { onNext: (account: Account) => void; onBack: () => void }) {
  const { data: accounts = [] } = useAccounts();
  const existing = accounts.filter((a) => a.type !== "cash");
  return (
    <div className="grid gap-7">
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.03em]">Where does your money live?</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-text-2">
          Add the bank account your salary or stipend lands in. You can add cards and UPI apps later — Spendzer will
          match payments that show up in more than one place.
        </p>
      </div>
      {existing.length > 0 && (
        <div className="grid gap-2">
          {existing.map((a) => {
            const Icon = accountIcon(a.type);
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => onNext(a)}
                className="flex items-center gap-3 rounded-xl border border-border px-4 py-3 text-left transition-colors hover:border-brand hover:bg-brand-soft/40"
              >
                <Icon className="size-4 text-text-3" />
                <span className="flex-1 text-sm font-medium">{a.name}</span>
                <span className="text-xs text-text-3">Use this one</span>
                <ArrowRight className="size-4 text-text-3" />
              </button>
            );
          })}
          <p className="pt-2 text-center text-xs text-text-3">or add another</p>
        </div>
      )}
      <AccountForm submitLabel="Add and continue" onCreated={onNext} autoFocus={existing.length === 0} />
      <Button variant="ghost" className="w-fit" onClick={onBack}>
        <ArrowLeft /> Back
      </Button>
    </div>
  );
}

function UploadStep({ account, onBack }: { account: Account; onBack: () => void }) {
  const navigate = useNavigate();
  const { data: sources = [] } = useSources();
  const create = useCreateUpload();
  const [sourceType, setSourceType] = useState(account.type === "upi" ? "gpay_pdf" : "generic_csv");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const source = sources.find((s) => s.source_type === sourceType);

  async function send(f: File, pdf_password?: string) {
    setFile(f);
    try {
      const upload = await create.mutateAsync({ file: f, account_id: account.id, source_type: sourceType, pdf_password });
      setActiveId(upload.id);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="grid gap-7">
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.03em]">Bring in last month's statement</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-text-2">
          Download it from net banking as CSV, Excel or PDF. It's read in memory and deleted straight after.
        </p>
      </div>
      {activeId ? (
        <ActiveUpload
          id={activeId}
          onReset={() => setActiveId(null)}
          onUnlock={async (password) => {
            if (file) await send(file, password);
          }}
        />
      ) : (
        <>
          <div className="grid gap-1.5">
            <p className="text-[13px] font-medium text-text-2">Statement type for {account.name}</p>
            <Select
              value={sourceType}
              onValueChange={setSourceType}
              options={sources.map((s) => ({ value: s.source_type, label: s.label }))}
            />
          </div>
          <UploadDropzone onFile={(f) => void send(f)} disabled={create.isPending} extensions={source?.extensions ?? [".csv", ".xls", ".xlsx"]} />
          <p className="flex items-center gap-2 text-xs text-text-3">
            <ShieldCheck className="size-3.5" /> Card numbers are masked to the last 4 digits before anything is saved.
          </p>
        </>
      )}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft /> Back
        </Button>
        <Button variant="link" onClick={() => navigate("/dashboard", { replace: true })}>
          {activeId ? "Go to my dashboard" : "Skip for now"}
        </Button>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [account, setAccount] = useState<Account | null>(null);
  const { user } = useAuth();

  useEffect(() => {
    document.title = "Set up Spendzer";
    return () => {
      document.title = "Spendzer — know where it went, plan where it goes";
    };
  }, []);

  return (
    <div className="min-h-dvh bg-background">
      <header className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
        <Link to="/dashboard">
          <Logo />
        </Link>
        <Link to="/dashboard" className="text-sm text-text-3 hover:text-text">
          Skip setup
        </Link>
      </header>
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-4 sm:px-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-text-2">Welcome{user ? `, ${user.name.split(" ")[0]}` : ""} — three quick steps.</p>
          <Progress step={step} />
        </div>
        <Card key={step} className="animate-fade-up p-6 sm:p-9">
          {step === 0 && <SavingsStep onNext={() => setStep(1)} />}
          {step === 1 && (
            <AccountStep
              onBack={() => setStep(0)}
              onNext={(a) => {
                setAccount(a);
                setStep(2);
              }}
            />
          )}
          {step === 2 && account && <UploadStep account={account} onBack={() => setStep(1)} />}
        </Card>
      </main>
    </div>
  );
}
