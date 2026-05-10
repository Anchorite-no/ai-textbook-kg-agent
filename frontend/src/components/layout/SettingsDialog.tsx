import * as Dialog from "@radix-ui/react-dialog";
import { CheckCircle2, Database, RefreshCw, Settings, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button, IconButton, Tag, Tooltip } from "@/components/_kit";
import { healthApi } from "@/api/health";
import { apiMode } from "@/api/registry";
import { useSevenBooksDatasetQuery } from "@/hooks/useTextbooks";
import { useUIStore } from "@/store/uiStore";

export interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const graphTopN = useUIStore((s) => s.graphTopN);
  const setGraphTopN = useUIStore((s) => s.setGraphTopN);
  const workflowUseLLM = useUIStore((s) => s.workflowUseLLM);
  const setWorkflowUseLLM = useUIStore((s) => s.setWorkflowUseLLM);
  const resetLeftWidth = useUIStore((s) => s.resetLeftWidth);
  const resetRightWidth = useUIStore((s) => s.resetRightWidth);
  const dataset = useSevenBooksDatasetQuery();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.getHealth,
    enabled: open,
    staleTime: 10_000
  });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/25 animate-fade-in z-40" />
        <Dialog.Content className="fixed right-4 top-16 z-50 w-[420px] max-w-[calc(100vw-32px)] rounded-card border border-border-soft bg-surface-card shadow-overlay animate-scale-in">
          <div className="px-4 py-3 border-b border-border-soft flex items-center gap-2">
            <Settings className="size-4 text-brand-600" />
            <Dialog.Title className="text-h2 text-text-strong">设置</Dialog.Title>
            <Dialog.Close asChild>
              <IconButton className="ml-auto" label="关闭设置" size="sm" icon={<X />} />
            </Dialog.Close>
          </div>

          <div className="p-4 flex flex-col gap-4">
            <section className="flex flex-col gap-2">
              <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">后端状态</h3>
              <div className="rounded-card border border-border-soft bg-surface-input p-3 flex items-center gap-2">
                <CheckCircle2 className="size-4 text-status-success" />
                <div className="min-w-0 flex-1">
                  <p className="text-body text-text-strong">
                    {health.data ? `${health.data.app} · ${health.data.version}` : health.isLoading ? "正在检查后端…" : "后端待检查"}
                  </p>
                  <p className="text-meta text-text-muted truncate">
                    {import.meta.env.VITE_API_BASE_URL || "Vite proxy /api -> 8010"}
                  </p>
                </div>
                <Tooltip content="刷新后端状态">
                  <IconButton
                    label="刷新后端状态"
                    tooltip={false}
                    size="sm"
                    icon={<RefreshCw className="size-3.5" />}
                    onClick={() => health.refetch()}
                  />
                </Tooltip>
              </div>
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">七本书数据集</h3>
              <div className="rounded-card border border-border-soft bg-surface-input p-3">
                <div className="flex items-center gap-2">
                  <Database className="size-4 text-brand-600" />
                  <span className="text-body text-text-strong">{dataset.data?.title ?? "七本医学教材"}</span>
                  <Tag size="sm" variant={dataset.data?.status === "ready" ? "success" : "warning"} className="ml-auto">
                    {dataset.data?.status ?? "unknown"}
                  </Tag>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-meta text-text-muted tabular">
                  <span>{dataset.data?.book_count ?? 0} 本书</span>
                  <span>{Number(dataset.data?.metrics?.chunk_count ?? 0).toLocaleString()} chunks</span>
                  <span>{Number(dataset.data?.metrics?.node_count ?? 0).toLocaleString()} 节点</span>
                </div>
              </div>
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">生成参数</h3>
              <label className="flex items-center justify-between gap-3 rounded-control bg-surface-input px-3 py-2">
                <span className="text-body text-text-default">上传后启用 LLM 抽取</span>
                <input
                  type="checkbox"
                  checked={workflowUseLLM}
                  onChange={(e) => setWorkflowUseLLM(e.target.checked)}
                  className="size-4 accent-brand-600"
                />
              </label>
              <label className="flex items-center justify-between gap-3 rounded-control bg-surface-input px-3 py-2">
                <span className="text-body text-text-default">图谱首屏节点数</span>
                <input
                  type="number"
                  min={50}
                  max={1000}
                  value={graphTopN}
                  onChange={(e) => setGraphTopN(Number(e.target.value) || 200)}
                  className="w-24 h-7 px-2 rounded-control border border-border-soft bg-surface-card text-meta text-text-default"
                />
              </label>
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">接口模式</h3>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(apiMode).map(([key, value]) => (
                  <Tag key={key} size="sm" variant={value === "live" ? "success" : "warning"}>
                    {key}: {value}
                  </Tag>
                ))}
              </div>
            </section>

            <div className="flex justify-end gap-2 pt-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  resetLeftWidth();
                  resetRightWidth();
                }}
              >
                重置布局
              </Button>
              <Button variant="primary" size="sm" onClick={() => onOpenChange(false)}>
                完成
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
