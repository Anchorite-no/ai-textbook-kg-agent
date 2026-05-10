import { GitMerge, TrendingDown, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { EmptyState, Tag, ErrorState } from "@/components/_kit";
import { integrationApi } from "@/api/integration";
import type { IntegrationDecision, IntegrationAction } from "@/types/api";

const ACTION_TAG: Record<IntegrationAction, { label: string; variant: "brand" | "success" | "warning" | "error" | "info" | "outline" }> = {
  merge: { label: "合并", variant: "brand" },
  keep: { label: "保留", variant: "success" },
  remove: { label: "移除", variant: "error" },
  refine: { label: "细化", variant: "info" },
  conflict: { label: "冲突", variant: "warning" }
};

export function IntegrationPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["integration"],
    queryFn: () => integrationApi.getIntegration(),
    retry: false
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="size-5 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-4">
        <EmptyState
          icon={<GitMerge />}
          title="整合面板"
          description="完成图谱构建后这里会显示压缩比、决策列表与冲突。"
        />
      </div>
    );
  }

  const stats = data.compression_stats;

  return (
    <div className="flex flex-col gap-4 p-4 scroll-region">
      {/* Compression card */}
      <div className="rounded-card border border-border-soft bg-surface-card p-3">
        <div className="flex items-center gap-2 mb-3">
          <TrendingDown className="size-4 text-brand-600" aria-hidden />
          <h3 className="text-h2 text-text-strong">压缩统计</h3>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Metric
            label="节点"
            before={stats.original_node_count}
            after={stats.integrated_node_count}
          />
          <Metric
            label="边"
            before={stats.original_edge_count}
            after={stats.integrated_edge_count}
          />
        </div>
        <div className="mt-3 flex items-center gap-2 text-meta text-text-muted">
          <span>压缩率</span>
          <Tag variant="success" size="sm">
            {(stats.compression_ratio * 100).toFixed(1)}%
          </Tag>
          <span className="text-text-subtle">（目标 {(stats.target_compression_ratio * 100).toFixed(0)}%）</span>
        </div>
      </div>

      {/* Decision list */}
      <div className="flex flex-col gap-2">
        <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">
          整合决策（{data.decisions.length}）
        </h3>
        {data.decisions.length === 0 ? (
          <p className="text-meta text-text-muted text-center py-4">暂无整合决策</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {data.decisions.map((d) => (
              <DecisionRow key={d.id} decision={d} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Metric({ label, before, after }: { label: string; before: number; after: number }) {
  const rate = before > 0 ? ((1 - after / before) * 100).toFixed(1) : "0";
  return (
    <div className="flex flex-col gap-1">
      <span className="text-meta text-text-muted">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="text-h1 text-text-strong tabular">{after}</span>
        <span className="text-meta text-text-subtle line-through tabular">{before}</span>
      </div>
      <Tag variant="success" size="sm" className="self-start">
        ↓ {rate}%
      </Tag>
    </div>
  );
}

function DecisionRow({ decision }: { decision: IntegrationDecision }) {
  const tag = ACTION_TAG[decision.action] ?? { label: decision.action, variant: "outline" as const };
  return (
    <li className="flex items-start gap-2 p-2.5 rounded-control bg-surface-input">
      <Tag size="sm" variant={tag.variant} className="shrink-0 mt-0.5">
        {tag.label}
      </Tag>
      <div className="flex flex-col gap-0.5 min-w-0 flex-1">
        <span className="text-meta text-text-default line-clamp-2">{decision.reason}</span>
        {decision.retained_content ? (
          <span className="text-[11px] text-text-muted">
            保留：{decision.retained_content}
            {decision.removed_redundancy ? ` ← 移除：${decision.removed_redundancy}` : ""}
          </span>
        ) : null}
      </div>
      <span className="text-[11px] text-text-subtle tabular shrink-0 mt-0.5">
        {(decision.confidence * 100).toFixed(0)}%
      </span>
    </li>
  );
}
