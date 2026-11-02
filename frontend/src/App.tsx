import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";

import { AppShell } from "@/components/AppShell";
import { LogoMark } from "@/components/Logo";
import { TooltipProvider } from "@/components/ui/overlays";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { LoginPage, RegisterPage } from "@/pages/AuthPages";
import { LandingPage } from "@/pages/LandingPage";

const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const TransactionsPage = lazy(() => import("@/pages/TransactionsPage"));
const UploadPage = lazy(() => import("@/pages/UploadPage"));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const PlannerPage = lazy(() => import("@/pages/PlannerPage"));
const RecurringPage = lazy(() => import("@/pages/RecurringPage"));
const ReviewQueuePage = lazy(() => import("@/pages/ReviewQueuePage"));
const MonthReviewPage = lazy(() => import("@/pages/MonthReviewPage"));
const OnboardingPage = lazy(() => import("@/pages/OnboardingPage"));
const PlanIndexRedirect = lazy(() =>
  import("@/pages/PlannerPage").then((m) => ({ default: m.PlanIndexRedirect })),
);

function Splash() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <LogoMark className="size-10 animate-pulse" />
    </div>
  );
}

function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Splash />;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

function GuestOnly() {
  const { status } = useAuth();
  if (status === "loading") return <Splash />;
  if (status === "authenticated") return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

function ThemedToaster() {
  const { theme } = useTheme();
  return (
    <Toaster
      position="bottom-right"
      theme={theme}
      toastOptions={{
        className: "!rounded-xl !border-border !bg-surface !text-text !shadow-[var(--shadow-pop)] !font-sans",
      }}
    />
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <TooltipProvider>
          <Suspense fallback={<Splash />}>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route element={<GuestOnly />}>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
              </Route>
              <Route element={<RequireAuth />}>
                <Route path="/onboarding" element={<OnboardingPage />} />
                <Route element={<AppShell />}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/transactions" element={<TransactionsPage />} />
                  <Route path="/upload" element={<UploadPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/plan" element={<PlanIndexRedirect />} />
                  <Route path="/plan/:month" element={<PlannerPage />} />
                  <Route path="/recurring" element={<RecurringPage />} />
                  <Route path="/review" element={<ReviewQueuePage />} />
                  <Route path="/review/:month" element={<MonthReviewPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          <ThemedToaster />
        </TooltipProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
