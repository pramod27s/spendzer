import { useMemo } from "react";

import { useCategories } from "@/api/queries";
import type { Category } from "@/api/types";

export function useCategoryMap() {
  const { data } = useCategories();
  return useMemo(() => {
    const map = new Map<string, Category>();
    for (const c of data ?? []) map.set(c.id, c);
    return map;
  }, [data]);
}
