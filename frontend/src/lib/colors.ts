// Categorical slots from the validated data-viz palette. Categories store the light hex;
// each maps to a CSS variable so dark mode swaps in that slot's dark step automatically.
export const SERIES_VARS = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
] as const;

const LIGHT_TO_SLOT: Record<string, number> = {
  "#2a78d6": 0,
  "#eb6834": 1,
  "#1baf7a": 2,
  "#eda100": 3,
  "#e87ba4": 4,
  "#008300": 5,
  "#6250d6": 6,
  "#e34948": 7,
};

export const MUTED_SERIES = "var(--series-muted)";

/** CSS colour for a stored category hex (theme-aware for palette slots). */
export function categoryColor(hex: string | undefined | null): string {
  if (!hex) return MUTED_SERIES;
  const slot = LIGHT_TO_SLOT[hex.toLowerCase()];
  return slot === undefined ? (hex.toLowerCase() === "#898781" ? MUTED_SERIES : hex) : SERIES_VARS[slot];
}

/**
 * Colours for a chart showing several categories at once. Each category keeps its own hue;
 * if two visible categories share a hue (rarer categories reuse slots), the later one takes
 * the first unused slot so no two visible slices look alike.
 */
export function distinctCategoryColors(hexes: (string | null | undefined)[]): string[] {
  const used = new Set<number>();
  const out: string[] = [];
  for (const hex of hexes) {
    const slot = hex ? LIGHT_TO_SLOT[hex.toLowerCase()] : undefined;
    if (slot === undefined) {
      out.push(MUTED_SERIES);
      continue;
    }
    if (!used.has(slot)) {
      used.add(slot);
      out.push(SERIES_VARS[slot]);
      continue;
    }
    const free = SERIES_VARS.findIndex((_, i) => !used.has(i));
    if (free === -1) {
      out.push(MUTED_SERIES);
    } else {
      used.add(free);
      out.push(SERIES_VARS[free]);
    }
  }
  return out;
}
