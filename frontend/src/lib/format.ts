// Money arrives from the API as strings ("1234.50") so no precision is lost in JSON.
export type MoneyLike = string | number | null | undefined;

export function toNumber(value: MoneyLike): number {
  if (value === null || value === undefined || value === "") return 0;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

const inr0 = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
const inr2 = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** ₹1,23,456 — Indian digit grouping. `paise` shows two decimals. */
export function formatINR(value: MoneyLike, opts: { paise?: boolean; sign?: boolean } = {}): string {
  const n = toNumber(value);
  const body = (opts.paise ? inr2 : inr0).format(Math.abs(n));
  if (n < 0) return `−${body}`;
  if (opts.sign && n > 0) return `+${body}`;
  return body;
}

/** Compact axis labels: ₹950, ₹12K, ₹1.2L, ₹3.4Cr. */
export function formatCompactINR(value: MoneyLike): string {
  const n = toNumber(value);
  const abs = Math.abs(n);
  const sign = n < 0 ? "−" : "";
  const trim = (x: number) => (x >= 10 ? x.toFixed(0) : x.toFixed(1).replace(/\.0$/, ""));
  if (abs >= 1e7) return `${sign}₹${trim(abs / 1e7)}Cr`;
  if (abs >= 1e5) return `${sign}₹${trim(abs / 1e5)}L`;
  if (abs >= 1e3) return `${sign}₹${trim(abs / 1e3)}K`;
  return `${sign}₹${Math.round(abs)}`;
}

export function formatPct(value: MoneyLike, digits = 1): string {
  return `${toNumber(value).toFixed(digits).replace(/\.0$/, "")}%`;
}

/** Percent change between two amounts; null when there's no base to compare to. */
export function pctChange(current: MoneyLike, previous: MoneyLike): number | null {
  const prev = toNumber(previous);
  if (prev === 0) return null;
  return ((toNumber(current) - prev) / Math.abs(prev)) * 100;
}

const dayFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const dayYearFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const monthFmt = new Intl.DateTimeFormat("en-IN", { month: "short" });
const monthYearFmt = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" });

/** Parse YYYY-MM-DD as a local date (no timezone shift). */
export function parseISODate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export function toISODate(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function formatDay(iso: string, withYear = false): string {
  return (withYear ? dayYearFmt : dayFmt).format(parseISODate(iso));
}

export function formatMonthShort(yyyyMm: string): string {
  return monthFmt.format(parseISODate(`${yyyyMm}-01`));
}

export function formatMonthLong(d: Date): string {
  return monthYearFmt.format(d);
}

export function monthBounds(d: Date): { start: string; end: string } {
  const start = new Date(d.getFullYear(), d.getMonth(), 1);
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return { start: toISODate(start), end: toISODate(end) };
}

export function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** "19:23:00" -> "7:23 pm" (Indian convention: 12-hour, lowercase). */
export function formatTime(hhmmss: string | null | undefined): string {
  if (!hhmmss) return "";
  const [h, m] = hhmmss.split(":").map(Number);
  const suffix = h >= 12 ? "pm" : "am";
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${suffix}`;
}
