import { CircleCheck, Lightbulb, TrendingUp } from "lucide-react";

import { useInsights } from "@/api/queries";
import type { Insight } from "@/api/types";
import { CategoryDot } from "@/components/common";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { useCategoryMap } from "@/hooks/useCategoryMap";
import { cn } from "@/lib/utils";

const TONE = {
  good: { icon: CircleCheck, ring: "bg-good-soft text-good-ink", label: "Good news" },
  bad: { icon: TrendingUp, ring: "bg-critical-soft text-critical-ink", label: "Worth a look" },
  neutral: { icon: Lightbulb, ring: "bg-brand-soft text-brand-ink", label: "Insight" },
} as const;

export function InsightCard({ insight }: { insight: Insight }) {
  const categories = useCategoryMap();
  const cat = insight.category_id ? categories.get(insight.category_id) : null;
  const tone = TONE[insight.tone];
  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-surface p-4 transition-shadow hover:shadow-[var(--shadow-pop)]">
      <div className="flex items-center gap-2.5">
        {cat ? (
          <CategoryDot category={cat} size="sm" />
        ) : (
          <span className={cn("grid size-6 place-items-center rounded-md", tone.ring)}>
            <tone.icon className="size-3.5" />
          </span>
        )}
        <p className="truncate text-sm font-semibold">{insight.title}</p>
        <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10.5px] font-medium", tone.ring)}>{tone.label}</span>
      </div>
      <p className="mt-2.5 text-[13.5px] leading-relaxed text-text-2">{insight.body}</p>
    </div>
  );
}

export function InsightsPanel({ month, title = "Insights", description }: { month: string; title?: string; description?: string }) {
  const { data, isLoading } = useInsights(month);
  if (!isLoading && !data?.insights.length) return null;
  return (
    <Card>
      <CardHeader title={title} description={description ?? "What stood out, biggest impact first"} />
      <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
        {isLoading
          ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)
          : data!.insights.map((insight) => <InsightCard key={`${insight.kind}-${insight.category_id}-${insight.title}`} insight={insight} />)}
      </div>
    </Card>
  );
}
