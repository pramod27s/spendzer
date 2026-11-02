import { ArrowRight, Eye, EyeOff, ShieldCheck, Sparkles, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/primitives";
import { useAuth } from "@/hooks/useAuth";
import { DEMO_EMAIL, DEMO_PASSWORD } from "@/lib/demo";

function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: string; children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,560px)]">
      <div className="flex flex-col px-5 py-6 sm:px-10">
        <Link to="/" className="w-fit">
          <Logo />
        </Link>
        <div className="mx-auto flex w-full max-w-[380px] flex-1 flex-col justify-center py-12">
          <h1 className="text-[28px] font-semibold tracking-[-0.03em]">{title}</h1>
          <p className="mt-1.5 text-sm text-text-2">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-center text-sm text-text-2">{footer}</p>
        </div>
      </div>
      <aside className="relative hidden overflow-hidden border-l border-border bg-[#0f1211] p-10 text-[#f0efec] lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-40 -top-40 size-[520px] rounded-full bg-[radial-gradient(circle,rgba(47,191,155,0.28),transparent_65%)]" aria-hidden />
        <div className="absolute -bottom-48 -left-24 size-[480px] rounded-full bg-[radial-gradient(circle,rgba(57,135,229,0.18),transparent_65%)]" aria-hidden />
        <p className="relative text-sm text-[#a9a89f]">Spendzer</p>
        <div className="relative">
          <p className="text-[32px] font-semibold leading-[1.1] tracking-[-0.03em]">
            Know where it went.
            <span className="block text-[#7b7a73]">Plan where it goes.</span>
          </p>
          <ul className="mt-10 grid gap-4 text-[15px]">
            {[
              { icon: WandSparkles, text: "UPI, NEFT and card narrations turned into real merchants" },
              { icon: Sparkles, text: "Categories that learn from every correction you make" },
              { icon: ShieldCheck, text: "Statements parsed in memory, never stored" },
            ].map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/5">
                  <Icon className="size-4 text-[#5fd9b8]" />
                </span>
                <span className="pt-1 text-[#d6d5cd]">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-[#7b7a73]">Amounts in INR · made for students and early-career earners</p>
      </aside>
    </div>
  );
}

function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input {...props} type={show ? "text" : "password"} className="pr-10" />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute inset-y-0 right-0 grid w-10 place-items-center text-text-3 hover:text-text"
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="rounded-lg border border-critical/30 bg-critical-soft px-3 py-2.5 text-sm text-critical-ink">
      {message}
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);

  async function tryDemo() {
    setError(null);
    setDemoBusy(true);
    try {
      await login(DEMO_EMAIL, DEMO_PASSWORD);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "The demo isn't available right now."));
    } finally {
      setDemoBusy(false);
    }
  }

  // /login?demo=1 (the landing page's "Try the live demo") signs straight in.
  const wantsDemo = new URLSearchParams(location.search).get("demo") === "1";
  useEffect(() => {
    if (wantsDemo) void tryDemo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantsDemo]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : "/dashboard", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to see where your money went."
      footer={
        <>
          New to Spendzer?{" "}
          <Link to="/register" className="font-medium text-brand-ink hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-4" noValidate>
        <FormError message={error} />
        <Field label="Email" htmlFor="email">
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoFocus />
        </Field>
        <Field label="Password" htmlFor="password">
          <PasswordInput id="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Button type="submit" size="lg" loading={busy} className="mt-2 w-full">
          Sign in <ArrowRight />
        </Button>
        <div className="relative my-1 text-center text-xs text-text-3">
          <span className="absolute inset-x-0 top-1/2 h-px bg-border" aria-hidden />
          <span className="relative bg-background px-3">or</span>
        </div>
        <Button type="button" size="lg" variant="secondary" className="w-full" loading={demoBusy} onClick={() => void tryDemo()}>
          <Sparkles /> Explore the demo account
        </Button>
      </form>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
  const errors = {
    name: name.trim() ? null : "Tell us what to call you",
    email: emailOk ? null : "Enter a valid email address",
    password: password.length >= 8 ? null : "Use at least 8 characters",
  };
  const valid = !errors.name && !errors.email && !errors.password;
  const strength = Math.min(4, [password.length >= 8, password.length >= 12, /\d/.test(password), /[^A-Za-z0-9]/.test(password)].filter(Boolean).length);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!valid) return;
    setError(null);
    setBusy(true);
    try {
      await register(name.trim(), email.trim(), password);
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Two minutes from now you'll know where last month went."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand-ink hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-4" noValidate>
        <FormError message={error} />
        <Field label="Name" htmlFor="name" error={touched ? errors.name : null}>
          <Input id="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={touched && !!errors.name} autoFocus />
        </Field>
        <Field label="Email" htmlFor="email" error={touched ? errors.email : null}>
          <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} aria-invalid={touched && !!errors.email} placeholder="you@example.com" />
        </Field>
        <Field label="Password" htmlFor="password" error={touched ? errors.password : null} hint="At least 8 characters.">
          <PasswordInput id="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={touched && !!errors.password} />
          {password && (
            <div className="mt-1 grid grid-cols-4 gap-1" aria-hidden>
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className="h-1 rounded-full transition-colors"
                  style={{
                    background:
                      i < strength ? (strength <= 1 ? "var(--critical)" : strength === 2 ? "var(--warning)" : "var(--good)") : "var(--surface-3)",
                  }}
                />
              ))}
            </div>
          )}
        </Field>
        <Button type="submit" size="lg" loading={busy} className="mt-2 w-full">
          Create account <ArrowRight />
        </Button>
        <p className="text-center text-xs text-text-3">We never store your statement files.</p>
      </form>
    </AuthLayout>
  );
}
