import * as SliderPrimitive from "@radix-ui/react-slider";
import { Download, Ellipsis, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/api/client";
import {
  downloadTransactionsCsv,
  useAccounts,
  useCategories,
  useCreateCategory,
  useDeleteAccount,
  useDeleteCategory,
  useDeleteMe,
  useDeleteRule,
  useMerchantRules,
  useUpdateMe,
} from "@/api/queries";
import type { Account, Bucket, Category } from "@/api/types";
import { AccountDialog, accountIcon } from "@/components/AccountDialog";
import { PageHeader } from "@/components/AppShell";
import { CategoryDot, EmptyState } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/overlays";
import { Badge, Card, CardHeader, Field, Input } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { type ThemePref, useTheme } from "@/hooks/useTheme";
import { categoryColor } from "@/lib/colors";
import { ICON_CHOICES } from "@/lib/icons";
import { cn } from "@/lib/utils";

function Section({ title, description, children, action }: { title: string; description?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} description={description} action={action} />
      <div className="p-5">{children}</div>
    </Card>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const update = useUpdateMe();
  const [name, setName] = useState(user?.name ?? "");
  const [target, setTarget] = useState(Number(user?.monthly_savings_target_pct ?? 20));
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    if (user) {
      setName(user.name);
      setTarget(Number(user.monthly_savings_target_pct));
    }
  }, [user]);

  const dirty = user && (name.trim() !== user.name || target !== Number(user.monthly_savings_target_pct));

  return (
    <Section title="Profile" description="How Spendzer addresses you and what you aim to save.">
      <div className="grid gap-6 md:grid-cols-2">
        <Field label="Name" htmlFor="s-name">
          <Input id="s-name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Email" htmlFor="s-email">
          <Input id="s-email" value={user?.email ?? ""} disabled />
        </Field>
        <div className="grid gap-3 md:col-span-2">
          <div className="flex items-baseline justify-between">
            <p className="text-[13px] font-medium text-text-2">Monthly savings target</p>
            <p className="tabular text-2xl font-semibold tracking-tight">{target}%</p>
          </div>
          <SliderPrimitive.Root
            value={[target]}
            min={0}
            max={60}
            step={1}
            onValueChange={([v]) => setTarget(v)}
            className="relative flex h-5 w-full touch-none select-none items-center"
            aria-label="Monthly savings target"
          >
            <SliderPrimitive.Track className="relative h-1.5 grow overflow-hidden rounded-full bg-surface-3">
              <SliderPrimitive.Range className="absolute h-full rounded-full bg-brand" />
            </SliderPrimitive.Track>
            <SliderPrimitive.Thumb className="block size-5 rounded-full border-2 border-brand bg-surface shadow-[var(--shadow-pop)] transition-transform hover:scale-110 focus-visible:shadow-[0_0_0_4px_var(--ring)] focus-visible:outline-none" />
          </SliderPrimitive.Root>
          <p className="text-xs text-text-3">
            New plans set this share of your income aside before budgeting anything else. 20% is a solid start.
          </p>
        </div>
        <div className="grid gap-2 md:col-span-2">
          <p className="text-[13px] font-medium text-text-2">Appearance</p>
          <div className="flex gap-2">
            {(["light", "dark", "system"] as ThemePref[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTheme(t)}
                className={cn(
                  "rounded-lg border px-4 py-2 text-sm capitalize transition-all",
                  theme === t ? "border-brand bg-brand-soft text-brand-ink" : "border-border text-text-2 hover:border-border-strong",
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-6 flex justify-end">
        <Button
          disabled={!dirty || !name.trim()}
          loading={update.isPending}
          onClick={async () => {
            try {
              const u = await update.mutateAsync({ name: name.trim(), monthly_savings_target_pct: String(target) });
              setUser(u);
              toast.success("Profile saved");
            } catch (err) {
              toast.error(errorMessage(err));
            }
          }}
        >
          Save changes
        </Button>
      </div>
    </Section>
  );
}

function AccountsSection() {
  const { data: accounts = [] } = useAccounts();
  const remove = useDeleteAccount();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState<Account | null>(null);
  return (
    <Section
      title="Accounts"
      description="Banks, cards and UPI apps you upload statements from."
      action={
        <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
          <Plus /> Add
        </Button>
      }
    >
      <ul className="grid gap-2">
        {accounts.map((a) => {
          const Icon = accountIcon(a.type);
          return (
            <li key={a.id} className="flex items-center gap-3 rounded-xl border border-border px-3.5 py-3">
              <span className="grid size-9 place-items-center rounded-lg bg-surface-2 text-text-2">
                <Icon className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {a.name}
                  {a.last4 && <span className="tabular ml-1.5 text-text-3">••{a.last4}</span>}
                </p>
                <p className="truncate text-xs capitalize text-text-3">
                  {a.type === "upi" ? "UPI app" : a.type}
                  {a.institution && ` · ${a.institution}`}
                </p>
              </div>
              {a.has_column_mapping && <Badge tone="brand">Columns saved</Badge>}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${a.name}`}>
                    <Ellipsis />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem destructive onSelect={() => setConfirm(a)}>
                    <Trash2 /> Delete account
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </li>
          );
        })}
      </ul>
      <AccountDialog open={open} onOpenChange={setOpen} />
      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent title={`Delete ${confirm?.name}?`} description="Every upload and transaction from this account is deleted too. This can't be undone.">
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={async () => {
                if (!confirm) return;
                try {
                  await remove.mutateAsync(confirm.id);
                  toast.success("Account deleted");
                  setConfirm(null);
                } catch (err) {
                  toast.error(errorMessage(err));
                }
              }}
            >
              Delete everything
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Section>
  );
}

const BUCKETS: { value: Bucket; label: string }[] = [
  { value: "discretionary", label: "Discretionary" },
  { value: "variable", label: "Variable" },
  { value: "fixed", label: "Fixed" },
  { value: "income", label: "Income" },
  { value: "excluded", label: "Not counted" },
];
const SWATCHES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

function CategoriesSection() {
  const { data: categories = [] } = useCategories();
  const create = useCreateCategory();
  const remove = useDeleteCategory();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [bucket, setBucket] = useState<Bucket>("variable");
  const [icon, setIcon] = useState("circle");
  const [color, setColor] = useState(SWATCHES[0]);
  const custom = categories.filter((c) => !c.is_system);
  const system = categories.filter((c) => c.is_system);

  return (
    <Section
      title="Categories"
      description={`${system.length} built in${custom.length ? ` · ${custom.length} of yours` : ""}`}
      action={
        <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
          <Plus /> New category
        </Button>
      }
    >
      {custom.length > 0 && (
        <ul className="mb-5 grid gap-2 sm:grid-cols-2">
          {custom.map((c) => (
            <li key={c.id} className="flex items-center gap-3 rounded-xl border border-border px-3 py-2.5">
              <CategoryDot category={c} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{c.name}</span>
                <span className="block text-xs capitalize text-text-3">{c.bucket}</span>
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Delete ${c.name}`}
                onClick={async () => {
                  try {
                    await remove.mutateAsync(c.id);
                    toast.success(`${c.name} deleted`, { description: "Its transactions moved to Other." });
                  } catch (err) {
                    toast.error(errorMessage(err));
                  }
                }}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-1.5">
        {system.map((c) => (
          <span key={c.id} className="inline-flex items-center gap-1.5 rounded-full border border-border py-1 pl-1 pr-2.5 text-xs text-text-2">
            <CategoryDot category={c} size="sm" />
            {c.name}
          </span>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title="New category">
          <form
            className="grid gap-4"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!name.trim()) return;
              try {
                await create.mutateAsync({ name: name.trim(), bucket, icon, color });
                toast.success(`${name.trim()} created`);
                setName("");
                setOpen(false);
              } catch (err) {
                toast.error(errorMessage(err));
              }
            }}
          >
            <div className="flex items-center gap-3">
              <CategoryDot category={{ icon, color } as Category} size="lg" />
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Category name" maxLength={80} autoFocus />
            </div>
            <Field label="Type" htmlFor="c-bucket">
              <Select id="c-bucket" value={bucket} onValueChange={(v) => setBucket(v as Bucket)} options={BUCKETS} />
            </Field>
            <div className="grid gap-2">
              <p className="text-[13px] font-medium text-text-2">Colour</p>
              <div className="flex flex-wrap gap-2">
                {SWATCHES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setColor(s)}
                    className={cn("size-7 rounded-full transition-transform hover:scale-110", color === s && "ring-2 ring-offset-2 ring-offset-[var(--surface)]")}
                    style={{ background: categoryColor(s), ["--tw-ring-color" as string]: categoryColor(s) }}
                    aria-label={`Colour ${s}`}
                  />
                ))}
              </div>
            </div>
            <div className="grid gap-2">
              <p className="text-[13px] font-medium text-text-2">Icon</p>
              <div className="grid grid-cols-8 gap-1.5">
                {ICON_CHOICES.map((i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setIcon(i)}
                    className={cn("grid place-items-center rounded-lg p-1 transition-colors", icon === i ? "bg-surface-2 ring-1 ring-border-strong" : "hover:bg-surface-2")}
                    aria-label={i}
                  >
                    <CategoryDot category={{ icon: i, color } as Category} size="sm" />
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!name.trim()} loading={create.isPending}>
                Create
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </Section>
  );
}

function RulesSection() {
  const { data: rules = [] } = useMerchantRules();
  const { data: categories = [] } = useCategories();
  const remove = useDeleteRule();
  const byId = new Map(categories.map((c) => [c.id, c]));
  return (
    <Section title="Merchant rules" description="Created when you choose “Apply to all” on a transaction. Your rules always win.">
      {rules.length === 0 ? (
        <EmptyState compact icon={Sparkles} title="No rules yet" description="Recategorize a transaction and choose “Apply to all” to teach Spendzer." />
      ) : (
        <ul className="grid gap-2">
          {rules.map((r) => {
            const cat = byId.get(r.category_id);
            return (
              <li key={r.id} className="flex items-center gap-3 rounded-xl border border-border px-3.5 py-2.5">
                <span className="min-w-0 flex-1 truncate text-sm">
                  <span className="text-text-3">{r.match_type === "exact" ? "Merchant is" : r.match_type === "regex" ? "Matches" : "Contains"}</span>{" "}
                  <span className="font-medium">{r.pattern}</span>
                </span>
                <span className="hidden items-center gap-2 text-sm text-text-2 sm:flex">
                  → <CategoryDot category={cat} size="sm" /> {cat?.name}
                </span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Delete rule"
                  onClick={() => remove.mutate(r.id, { onSuccess: () => toast.success("Rule removed") })}
                >
                  <Trash2 />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function DataSection() {
  const { logout } = useAuth();
  const deleteMe = useDeleteMe();
  const [exporting, setExporting] = useState(false);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");

  return (
    <Section title="Your data" description="Take everything with you, or remove everything we hold.">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col justify-between gap-4 rounded-xl border border-border p-4">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold">
              <Download className="size-4 text-text-3" /> Export transactions
            </p>
            <p className="mt-1 text-[13px] text-text-2">
              Every transaction as a CSV — categories, notes, and which rows were duplicates.
            </p>
          </div>
          <Button
            variant="secondary"
            className="w-fit"
            loading={exporting}
            onClick={async () => {
              setExporting(true);
              try {
                await downloadTransactionsCsv();
              } catch (err) {
                toast.error(errorMessage(err));
              } finally {
                setExporting(false);
              }
            }}
          >
            Download CSV
          </Button>
        </div>
        <div className="flex flex-col justify-between gap-4 rounded-xl border border-critical/30 bg-critical-soft/40 p-4">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-critical-ink">
              <Trash2 className="size-4" /> Delete account
            </p>
            <p className="mt-1 text-[13px] text-text-2">
              Permanently removes your account, statements' transactions, plans, rules and alerts.
            </p>
          </div>
          <Button variant="danger" className="w-fit" onClick={() => setOpen(true)}>
            Delete my account
          </Button>
        </div>
      </div>
      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) {
            setPassword("");
            setConfirmText("");
          }
        }}
      >
        <DialogContent title="Delete your account?" description="This can't be undone. Download your data first if you want a copy.">
          <form
            className="grid gap-4"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await deleteMe.mutateAsync(password);
                toast.success("Your account and all its data are gone.");
                await logout().catch(() => undefined);
              } catch (err) {
                toast.error(errorMessage(err));
              }
            }}
          >
            <Field label='Type "delete" to confirm' htmlFor="del-confirm">
              <Input id="del-confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoComplete="off" />
            </Field>
            <Field label="Your password" htmlFor="del-password">
              <Input id="del-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </Field>
            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="danger" disabled={confirmText.trim().toLowerCase() !== "delete" || !password} loading={deleteMe.isPending}>
                Delete everything
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </Section>
  );
}

export default function SettingsPage() {
  return (
    <div className="animate-fade-up">
      <PageHeader title="Settings" description="Your profile, accounts and how Spendzer sorts your money." />
      <div className="grid gap-5">
        <ProfileSection />
        <div className="grid gap-5 xl:grid-cols-2">
          <AccountsSection />
          <RulesSection />
        </div>
        <CategoriesSection />
        <DataSection />
      </div>
    </div>
  );
}
