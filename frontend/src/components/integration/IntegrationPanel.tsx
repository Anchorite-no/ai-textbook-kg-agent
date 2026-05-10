import { GitMerge, TrendingDown, Loader2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, EmptyState, Tag } from "@/components/_kit";
import { integrationApi } from "@/api/integration";
import { toastStore } from "@/components/layout/ToastViewport";
import { useRawFileContext } from "@/hooks/useRawFileContext";
import type { IntegrationDecision, IntegrationAction } from "@/types/api";

const ACTION_TAG: Record<IntegrationAction, { label: string; variant: "brand" | "success" | "warning" | "error" | "info" | "outline" }> = {
  merge: { label: "合并", variant: "brand" },
  keep: { label: "保留", variant: "success" },
  remove: { label: "移除", variant: "error" },
  refine: { label: "细化", variant: "info" },
  conflict: { label: "冲突", variant: "warning" }
};
const OVERRIDE_ACTIONS: IntegrationAction[] = ["merge", "keep", "remove", "refine", "conflict"];

export function IntegrationPanel() {
  const queryClient = useQueryClient();
  const { rawFileIds } = useRawFileContext();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["integration", rawFileIds.join(",")],
    queryFn: () => integrationApi.getIntegration(rawFileIds),
    enabled: rawFileIds.length >= 2,
    retry: false
  });
  const edits = useQuery({
    queryKey: ["teacher-edits", rawFileIds.join(",")],
    queryFn: () => integrationApi.listTeacherEdits(rawFileIds),
    enabled: rawFileIds.length >= 2,
    retry: false
  });

  const build = useMutation({
    mutationFn: () => integrationApi.buildIntegration(rawFileIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["integration"] });
      toastStore.push({ tone: "success", title: "整合结果已生成" });
    },
    onError: (err) => {
      toastStore.push({
        tone: "error",
        title: "跨教材构建失败",
        description: err instanceof Error ? err.message : "请确认至少两本教材已经完成 KG 构建。"
      });
    }
  });

  const override = useMutation({
    mutationFn: ({ decision, action }: { decision: IntegrationDecision; action: IntegrationAction }) =>
      integrationApi.overrideDecision(decision.id, {
        raw_file_ids: rawFileIds,
        action,
        retained_content: decision.retained_content ?? decision.reason,
        removed_redundancy: decision.removed_redundancy ?? null,
        reason: `教师在前端将决策调整为 ${ACTION_TAG[action]?.label ?? action}`,
        confidence: 1,
        created_by: "teacher"
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["integration"] }),
        queryClient.invalidateQueries({ queryKey: ["teacher-edits"] }),
        queryClient.invalidateQueries({ queryKey: ["dialogue-history"] })
      ]);
      toastStore.push({ tone: "success", title: "教师覆盖已保存" });
    }
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
          description={rawFileIds.length < 2 ? "至少需要两本教材才能生成跨教材整合决策。" : "尚未读取到整合结果，可以直接构建。"}
          action={rawFileIds.length >= 2 ? (
            <Button variant="primary" loading={build.isPending} onClick={() => build.mutate()}>
              构建整合
            </Button>
          ) : undefined}
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
            label="节点压缩"
            before={stats.original_node_count}
            after={stats.integrated_node_count}
          />
          <Metric
            label="字符保留"
            before={stats.original_char_count}
            after={stats.retained_char_count}
          />
        </div>
        <div className="mt-3 flex items-center gap-2 text-meta text-text-muted">
          <span>压缩率</span>
          <Tag variant="success" size="sm">
            {(stats.compression_ratio * 100).toFixed(1)}%
          </Tag>
          <span className="text-text-subtle">（目标 {(stats.target_compression_ratio * 100).toFixed(0)}%）</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Tag size="sm" variant="brand">合并 {stats.merged_node_count}</Tag>
          <Tag size="sm" variant="success">保留 {stats.kept_node_count}</Tag>
          <Tag size="sm" variant="info">细化 {stats.refined_node_count}</Tag>
          <Tag size="sm" variant="warning">冲突 {stats.conflict_count}</Tag>
          <Tag size="sm" variant="outline">教师修改 {edits.data?.count ?? 0}</Tag>
        </div>
      </div>

      {/* Decision list */}
      <div className="flex flex-col gap-2">
        <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">
          整合决策（{(data.decisions ?? []).length}）
        </h3>
        {(data.decisions ?? []).length === 0 ? (
          <p className="text-meta text-text-muted text-center py-4">暂无整合决策</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {(data.decisions ?? []).map((d) => (
              <DecisionRow
                key={d.id}
                decision={d}
                onOverride={(action) => override.mutate({ decision: d, action })}
                disabled={override.isPending}
              />
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

function DecisionRow({
  decision,
  onOverride,
  disabled
}: {
  decision: IntegrationDecision;
  onOverride: (action: IntegrationAction) => void;
  disabled?: boolean;
}) {
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
      <div className="flex gap-1 shrink-0">
        {OVERRIDE_ACTIONS.map((action) => (
          <Button
            key={action}
            size="sm"
            variant="ghost"
            disabled={disabled || action === decision.action}
            onClick={() => onOverride(action)}
          >
            {ACTION_TAG[action].label}
          </Button>
        ))}
      </div>
    </li>
  );
}
