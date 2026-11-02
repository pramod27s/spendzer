import {
  ArrowRight,
  ArrowUpDown,
  CircleCheck,
  CloudUpload,
  EyeOff,
  FileSpreadsheet,
  KeyRound,
  ShieldCheck,
  Sparkles,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { CategoryDonut, type DonutDatum } from "@/components/charts/Charts";
import { CategoryDot } from "@/components/common";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { useAuth } from "@/hooks/useAuth";
import { SERIES_VARS } from "@/lib/colors";
import { formatINR } from "@/lib/format";
import { cn } from "@/lib/utils";

const NARRATIONS = [
  { raw: "UPI/DR/402918374651/SWIGGY/YESB/swiggy@ybl/Payment", merchant: "Swiggy", category: "Food & Dining", icon: "utensils", color: "#eb6834" },
  { raw: "UPI-ZOMATO LTD-zomato@hdfcbank-HDFC0000001-4029…", merchant: "Zomato", category: "Food & Dining", icon: "utensils", color: "#eb6834" },
  { raw: "POS 4591XXXXXXXX1234 AMAZON PAY IN", merchant: "Amazon", category: "Shopping", icon: "shopping-bag", color: "#e87ba4" },
  { raw: "NEFT-HDFCN52026110112-ACME TECH PVT LTD-SALARY", merchant: "Acme Tech (Salary)", category: "Salary", icon: "briefcase", color: "#1baf7a" },
  { raw: "ACH D- BAJAJ FINANCE LTD-P400XXXX", merchant: "Bajaj Finance", category: "EMI & Loans", icon: "landmark", color: "#e34948" },
];

const PREVIEW_SLICES: DonutDatum[] = [
  { key: "rent", name: "Rent", amount: 9000, pct: 41.2, color: SERIES_VARS[0], icon: "home", rawColor: "#2a78d6", count: 1 },
  { key: "food", name: "Food & Dining", amount: 5120, pct: 23.4, color: SERIES_VARS[1], icon: "utensils", rawColor: "#eb6834", count: 14 },
  { key: "groc", name: "Groceries", amount: 3240, pct: 14.8, color: SERIES_VARS[2], icon: "shopping-basket", rawColor: "#1baf7a", count: 9 },
  { key: "trans", name: "Transport", amount: 2210, pct: 10.1, color: SERIES_VARS[3], icon: "bus", rawColor: "#eda100", count: 18 },
  { key: "shop", name: "Shopping", amount: 1640, pct: 7.5, color: SERIES_VARS[4], icon: "shopping-bag", rawColor: "#e87ba4", count: 3 },
  { key: "subs", name: "Subscriptions", amount: 650, pct: 3.0, color: SERIES_VARS[6], icon: "repeat", rawColor: "#6250d6", count: 3 },
];

function NarrationTicker() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setI((n) => (n + 1) % NARRATIONS.length), 2600);
    return () => window.clearInterval(t);
  }, []);
  const item = NARRATIONS[i];
  return (
    <div className="grid gap-3">
      <div className="rounded-xl border border-dashed border-border-strong bg-surface-2/60 px-3.5 py-3">
        <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-text-3">Bank narration</p>
        <p key={item.raw} className="animate-fade-in truncate font-mono text-[12.5px] text-text-2">
          {item.raw}
        </p>
      </div>
      <div className="flex justify-center text-text-3">
        <WandSparkles className="size-4" />
      </div>
      <div key={item.merchant} className="flex animate-fade-up items-center gap-3 rounded-xl border border-border bg-surface px-3.5 py-3 shadow-[var(--shadow-card)]">
        <CategoryDot category={{ icon: item.icon, color: item.color }} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{item.merchant}</p>
          <p className="text-xs text-text-3">{item.category}</p>
        </div>
        <Badge tone="brand">
          <Sparkles /> Auto
        </Badge>
      </div>
    </div>
  );
}

function ProductPreview() {
  const rows = [
    { m: "Swiggy", c: { icon: "utensils", color: "#eb6834" }, cat: "Food & Dining", a: 450, d: "debit" as const },
    { m: "Acme Tech (Salary)", c: { icon: "briefcase", color: "#1baf7a" }, cat: "Salary", a: 30000, d: "credit" as const },
    { m: "Blinkit", c: { icon: "shopping-basket", color: "#1baf7a" }, cat: "Groceries", a: 780, d: "debit" as const },
    { m: "Uber", c: { icon: "bus", color: "#eda100" }, cat: "Transport", a: 230, d: "debit" as const },
  ];
  return (
    <div className="relative">
      <div className="absolute -inset-x-10 -inset-y-8 -z-10 rounded-[40px] bg-[radial-gradient(60%_60%_at_50%_40%,var(--brand-soft),transparent)]" aria-hidden />
      <Card className="overflow-hidden rounded-[22px] shadow-[var(--shadow-lift)]">
        <div className="flex items-center gap-1.5 border-b border-border bg-surface-2/60 px-4 py-3">
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="ml-3 text-xs text-text-3">October 2026 · preview with sample data</span>
        </div>
        <div className="grid gap-4 p-4 sm:p-5">
          <div className="grid grid-cols-3 gap-2.5">
            {[
              { l: "Income", v: 30112 },
              { l: "Spent", v: 21860 },
              { l: "Saved", v: 8252, good: true },
            ].map((k) => (
              <div key={k.l} className="rounded-xl border border-border bg-surface p-3">
                <p className="text-[11px] text-text-3">{k.l}</p>
                <p className={cn("tabular mt-1 text-[15px] font-semibold tracking-tight sm:text-lg", k.good && "text-good-ink")}>
                  {formatINR(k.v)}
                </p>
              </div>
            ))}
          </div>
          <div className="grid items-center gap-4 sm:grid-cols-[180px_1fr]">
            <CategoryDonut data={PREVIEW_SLICES} total={21860} size={170} />
            <ul className="grid gap-2">
              {PREVIEW_SLICES.slice(0, 4).map((s) => (
                <li key={s.key} className="flex items-center gap-2.5 text-[13px]">
                  <span className="h-4 w-1 rounded-full" style={{ background: s.color }} />
                  <span className="flex-1 truncate">{s.name}</span>
                  <span className="tabular text-text-2">{formatINR(s.amount)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-border">
            {rows.map((r, i) => (
              <div key={r.m} className={cn("flex items-center gap-3 px-3 py-2.5", i > 0 && "border-t border-border")}>
                <CategoryDot category={r.c} size="sm" />
                <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{r.m}</span>
                <span className="hidden text-xs text-text-3 sm:inline">{r.cat}</span>
                <span className={cn("tabular text-[13px] font-medium", r.d === "credit" && "text-good-ink")}>
                  {r.d === "credit" ? "+" : "−"}
                  {formatINR(r.a)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}

const STEPS = [
  {
    icon: CloudUpload,
    title: "Upload a statement",
    body: "CSV or Excel export from any bank. Map the columns once — Spendzer remembers them for that account.",
  },
  {
    icon: WandSparkles,
    title: "We clean every line",
    body: "UPI, NEFT, POS and ACH narrations become real merchant names, sorted into categories automatically.",
  },
  {
    icon: ArrowUpDown,
    title: "See the real picture",
    body: "Income vs spending, savings rate, where each rupee went — with refunds and self-transfers kept out.",
  },
];

const PRIVACY = [
  { icon: Trash2, title: "Raw files deleted", body: "Statements are parsed in memory and discarded. Never stored." },
  { icon: KeyRound, title: "Passwords never kept", body: "PDF passwords are used once to decrypt, never saved or logged." },
  { icon: EyeOff, title: "Card numbers masked", body: "Full card and account numbers are cut to the last four digits." },
  { icon: ShieldCheck, title: "Your data, your call", body: "Every query is scoped to you. Export or delete it any time." },
];

export function LandingPage() {
  const { status } = useAuth();
  const authed = status === "authenticated";
  return (
    <div className="min-h-dvh overflow-x-hidden">
      <header className="sticky top-0 z-40 border-b border-transparent bg-background/75 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-1 sm:gap-2">
            <a href="#how" className="hidden rounded-lg px-3 py-2 text-sm text-text-2 hover:text-text sm:block">
              How it works
            </a>
            <a href="#privacy" className="hidden rounded-lg px-3 py-2 text-sm text-text-2 hover:text-text sm:block">
              Privacy
            </a>
            {authed ? (
              <Button asChild size="sm">
                <Link to="/dashboard">Open dashboard</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/login">Sign in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/register">Get started</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="bg-dots absolute inset-0 -z-10 [mask-image:radial-gradient(70%_60%_at_50%_0%,black,transparent)] opacity-60" aria-hidden />
        <div className="mx-auto grid max-w-[1200px] items-center gap-14 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[1.2fr_1fr] lg:pt-24">
          <div className="animate-fade-up">
            <Badge tone="brand" className="mb-6 px-3 py-1 text-[12.5px]">
              <Sparkles /> Built for UPI-first India
            </Badge>
            <h1 className="text-balance text-[44px] font-semibold leading-[1.04] tracking-[-0.045em] sm:text-[58px] xl:text-[62px]">
              Know where it went.
              <span className="block text-text-3">Plan where it goes.</span>
            </h1>
            <p className="mt-6 max-w-lg text-[17px] leading-relaxed text-text-2">
              Spendzer turns your bank, UPI and card statements into a clear picture of your money — every
              Swiggy order, every auto-debit, every rupee of salary — sorted and summed for you.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" variant="brand">
                <Link to={authed ? "/dashboard" : "/register"}>
                  {authed ? "Go to dashboard" : "Start free"} <ArrowRight />
                </Link>
              </Button>
              {authed ? (
                <Button asChild size="lg" variant="secondary">
                  <a href="#how">See how it works</a>
                </Button>
              ) : (
                <Button asChild size="lg" variant="secondary">
                  <Link to="/login?demo=1">
                    <Sparkles /> Try the live demo
                  </Link>
                </Button>
              )}
            </div>
            <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-[13px] text-text-3">
              <span className="inline-flex items-center gap-1.5">
                <FileSpreadsheet className="size-4" /> Any bank's CSV or Excel
              </span>
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="size-4" /> Raw files never stored
              </span>
            </div>
          </div>
          <div className="animate-fade-up [animation-delay:120ms]">
            <ProductPreview />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 border-y border-border bg-surface/50">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-brand-ink">How it works</p>
            <h2 className="mt-2 text-balance text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
              From a messy statement to a clear month, in under a minute.
            </h2>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <Card key={s.title} className="p-6">
                <div className="flex items-center justify-between">
                  <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand-ink">
                    <s.icon className="size-5" />
                  </span>
                  <span className="font-mono text-xs text-text-3">0{i + 1}</span>
                </div>
                <h3 className="mt-5 text-[17px] font-semibold tracking-tight">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-2">{s.body}</p>
              </Card>
            ))}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.1fr]">
            <Card className="p-6">
              <h3 className="text-[17px] font-semibold tracking-tight">Narrations, decoded</h3>
              <p className="mt-1.5 text-sm text-text-2">
                Bank gibberish in, a merchant you recognise out — then it learns from every correction you make.
              </p>
              <div className="mt-6">
                <NarrationTicker />
              </div>
            </Card>
            <Card className="p-6">
              <h3 className="text-[17px] font-semibold tracking-tight">Only real income, only real spending</h3>
              <p className="mt-1.5 text-sm text-text-2">
                Moving money between your own accounts isn't spending. A refund isn't income. Spendzer knows the difference.
              </p>
              <ul className="mt-6 grid gap-2.5">
                {[
                  { label: "Salary from Acme Tech", tag: "Income", tone: "good" as const, amt: "+₹30,000" },
                  { label: "Amazon order refunded", tag: "Refund · excluded", tone: "neutral" as const, amt: "+₹1,299" },
                  { label: "To own SBI account ••4321", tag: "Self-transfer · excluded", tone: "neutral" as const, amt: "−₹5,000" },
                  { label: "Paytm cashback", tag: "Cashback · excluded", tone: "neutral" as const, amt: "+₹25" },
                ].map((r) => (
                  <li key={r.label} className="flex items-center gap-3 rounded-xl border border-border px-3.5 py-3">
                    <CircleCheck className={cn("size-4 shrink-0", r.tone === "good" ? "text-good" : "text-text-3")} />
                    <span className="min-w-0 flex-1 truncate text-sm">{r.label}</span>
                    <Badge tone={r.tone}>{r.tag}</Badge>
                    <span className="tabular hidden w-20 text-right text-sm font-medium sm:block">{r.amt}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      </section>

      {/* Privacy */}
      <section id="privacy" className="scroll-mt-20">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="overflow-hidden rounded-[28px] bg-[#0f1211] px-6 py-12 text-[#f0efec] sm:px-12 sm:py-14">
            <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
              <div>
                <p className="text-sm font-medium text-[#5fd9b8]">Privacy by default</p>
                <h2 className="mt-2 text-balance text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
                  Your complete financial history deserves better than "trust us".
                </h2>
                <p className="mt-4 text-[15px] leading-relaxed text-[#c3c2b7]">
                  These aren't settings you have to find. They're how Spendzer is built.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {PRIVACY.map((p) => (
                  <div key={p.title} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                    <p.icon className="size-5 text-[#5fd9b8]" />
                    <p className="mt-3 font-semibold">{p.title}</p>
                    <p className="mt-1 text-sm leading-relaxed text-[#a9a89f]">{p.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-4 pb-24 text-center sm:px-6">
        <h2 className="text-balance text-3xl font-semibold tracking-[-0.03em] sm:text-[40px]">
          Your money has a story. Read it.
        </h2>
        <p className="mx-auto mt-3 max-w-md text-text-2">
          Upload last month's statement and see where it went in less time than it takes to order chai.
        </p>
        <Button asChild size="lg" variant="brand" className="mt-8">
          <Link to={authed ? "/upload" : "/register"}>
            Get started <ArrowRight />
          </Link>
        </Button>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-8 text-sm text-text-3 sm:flex-row sm:px-6">
          <Logo className="opacity-80" />
          <p>know where it went, plan where it goes.</p>
        </div>
      </footer>
    </div>
  );
}
