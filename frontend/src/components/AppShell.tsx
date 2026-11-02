import {
  ArrowUpDown,
  ChartPie,
  CloudUpload,
  LayoutDashboard,
  LogOut,
  Inbox,
  Monitor,
  Moon,
  Repeat,
  Settings,
  Sun,
  Target,
} from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useReviewQueue } from "@/api/queries";
import { AlertBell } from "@/components/AlertBell";
import { Logo } from "@/components/Logo";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/overlays";
import { useAuth } from "@/hooks/useAuth";
import { type ThemePref, useTheme } from "@/hooks/useTheme";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, mobile: true },
  { to: "/plan", label: "Planner", icon: Target, mobile: true },
  { to: "/transactions", label: "Transactions", icon: ArrowUpDown, mobile: true },
  { to: "/upload", label: "Upload", icon: CloudUpload, mobile: true },
  { to: "/analytics", label: "Analytics", icon: ChartPie, mobile: true },
  { to: "/review", label: "Review", icon: Inbox, mobile: false },
  { to: "/recurring", label: "Recurring", icon: Repeat, mobile: false },
  { to: "/settings", label: "Settings", icon: Settings, mobile: false },
] as const;

const THEMES: { value: ThemePref; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function UserMenu({ compact = false }: { compact?: boolean }) {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex items-center gap-2.5 rounded-xl text-left transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
          compact ? "p-1" : "w-full p-2",
        )}
        aria-label="Account menu"
      >
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand to-[var(--series-1)] text-xs font-semibold text-white">
          {initials(user.name)}
        </span>
        {!compact && (
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{user.name}</span>
            <span className="block truncate text-xs text-text-3">{user.email}</span>
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align={compact ? "end" : "start"} side={compact ? "bottom" : "top"} className="w-60">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <div className="grid grid-cols-3 gap-1 px-1 pb-1">
          {THEMES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setTheme(value)}
              className={cn(
                "flex flex-col items-center gap-1 rounded-lg py-2 text-xs transition-colors",
                theme === value ? "bg-brand-soft text-brand-ink" : "text-text-2 hover:bg-surface-2",
              )}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/review")} className="lg:hidden">
          <Inbox /> Review
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate("/recurring")} className="lg:hidden">
          <Repeat /> Recurring
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate("/settings")} className="lg:hidden">
          <Settings /> Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SideNav() {
  const { data: queue } = useReviewQueue();
  const reviewCount = queue?.total ?? 0;
  return (
    <aside className="sticky top-0 hidden h-dvh w-[248px] shrink-0 flex-col border-r border-border bg-surface/60 px-3 py-5 backdrop-blur lg:flex">
      <div className="flex items-center justify-between pb-6 pl-2.5">
        <Logo />
        <AlertBell />
      </div>
      <nav className="grid gap-0.5" aria-label="Main">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-surface-2 text-text shadow-[inset_0_0_0_1px_var(--border)]"
                  : "text-text-2 hover:bg-surface-2/70 hover:text-text",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn("size-[18px]", isActive ? "text-brand" : "text-text-3 group-hover:text-text-2")} />
                {label}
                {to === "/review" && reviewCount > 0 && (
                  <span className="tabular ml-auto rounded-full bg-warning-soft px-1.5 py-0.5 text-[11px] font-semibold text-warning-ink">
                    {reviewCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto">
        <div className="mb-3 rounded-xl border border-border bg-surface-2/60 p-3.5">
          <p className="text-[13px] font-medium">Know where it went.</p>
          <p className="mt-0.5 text-xs leading-relaxed text-text-3">
            Upload each month's statement to keep your picture current.
          </p>
        </div>
        <UserMenu />
      </div>
    </aside>
  );
}

function MobileHeader() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-xl lg:hidden">
      <Logo />
      <div className="flex items-center gap-1">
        <AlertBell />
        <UserMenu compact />
      </div>
    </header>
  );
}

function BottomNav() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
      aria-label="Main"
    >
      <div className="grid grid-cols-5">
        {NAV.filter((n) => n.mobile).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors",
                isActive ? "text-brand-ink" : "text-text-3",
              )
            }
          >
            <Icon className="size-5" />
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  return (
    <div className="flex min-h-dvh">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        <main key={pathname} className="mx-auto w-full max-w-[1240px] flex-1 px-4 pb-28 pt-6 sm:px-6 lg:px-10 lg:pb-12 lg:pt-9">
          <Outlet />
        </main>
      </div>
      <BottomNav />
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1 text-sm text-text-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
