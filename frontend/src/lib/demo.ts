// The shared demo account (synthetic data, reset by `python -m app.seed.demo`).
export const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? "demo@spendzer.app";
export const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? "spendzer-demo";
