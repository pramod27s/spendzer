import { useSyncExternalStore } from "react";

export type ThemePref = "light" | "dark" | "system";
const KEY = "spendzer-theme";

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

const media = window.matchMedia("(prefers-color-scheme: dark)");
let pref: ThemePref = readPref();
const listeners = new Set<() => void>();

function apply() {
  const dark = pref === "dark" || (pref === "system" && media.matches);
  document.documentElement.classList.toggle("dark", dark);
}

media.addEventListener("change", () => {
  if (pref === "system") apply();
});

function setTheme(next: ThemePref) {
  try {
    if (next === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, next);
  } catch {
    /* storage unavailable: the theme still applies for this session */
  }
  pref = next;
  apply();
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** One theme store shared by every component (desktop + mobile menus stay in sync). */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, () => pref);
  return { theme, setTheme };
}
