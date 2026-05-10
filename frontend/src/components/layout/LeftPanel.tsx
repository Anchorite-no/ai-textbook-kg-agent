/** 左栏：教材区。UploadZone + TextbookList + ChapterTree。 */

import { BookOpen, Plus, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, EmptyState, IconButton, Tooltip } from "@/components/_kit";
import { useUIStore } from "@/store/uiStore";
import { useTextbooksQuery } from "@/hooks/useTextbooks";
import { jobsApi } from "@/api/jobs";
import { workflowsApi } from "@/api/workflows";
import { toastStore } from "@/components/layout/ToastViewport";
import { UploadZone } from "@/components/textbooks/UploadZone";
import { TextbookList } from "@/components/textbooks/TextbookList";
import { ChapterTree } from "@/components/textbooks/ChapterTree";

export function LeftPanel() {
  const queryClient = useQueryClient();
  const collapsed = useUIStore((s) => s.leftCollapsed);
  const toggleLeftCollapsed = useUIStore((s) => s.toggleLeftCollapsed);
  const selectedTextbookId = useUIStore((s) => s.selectedTextbookId);
  const setSelectedTextbookId = useUIStore((s) => s.setSelectedTextbookId);
  const setWorkspaceRawFileIds = useUIStore((s) => s.setWorkspaceRawFileIds);
  const workflowUseLLM = useUIStore((s) => s.workflowUseLLM);
  const { data: textbooks, isLoading } = useTextbooksQuery();
  const [showUpload, setShowUpload] = useState(false);

  useEffect(() => {
    if (!selectedTextbookId && textbooks?.[0]?.raw_file_id) {
      setSelectedTextbookId(textbooks[0].raw_file_id);
    }
  }, [selectedTextbookId, setSelectedTextbookId, textbooks]);

  const uploadWorkflow = useMutation({
    mutationFn: async (files: File[]) => {
      const accepted = await workflowsApi.organizeFiles(files, {
        useLlm: workflowUseLLM,
        buildGraph: true,
        buildLayeredGraphs: true,
        buildRag: true,
        buildAlignmentGraph: true,
        buildIntegrationResult: true,
        maxSections: 300,
        maxNodesPerSection: 12,
        alignmentMinConfidence: 0.62
      });
      return jobsApi.waitForJob(accepted.job.id, 300_000);
    },
    onSuccess: async (job) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["textbooks"] }),
        queryClient.invalidateQueries({ queryKey: ["dataset", "seven-books"] }),
        queryClient.invalidateQueries({ queryKey: ["graph"] }),
        queryClient.invalidateQueries({ queryKey: ["integration"] }),
        queryClient.invalidateQueries({ queryKey: ["rag"] }),
        queryClient.invalidateQueries({ queryKey: ["dialogue-history"] })
      ]);
      const rawFileIds = rawIdsFromJob(job.result);
      if (rawFileIds.length) {
        setWorkspaceRawFileIds(rawFileIds);
        setSelectedTextbookId(rawFileIds[0]);
      }
      setShowUpload(false);
      toastStore.push({
        tone: "success",
        title: "文件已整理生成",
        description: `${rawFileIds.length || 1} 个文件已完成解析、图谱、RAG 和整合流程`
      });
    }
  });

  function handleUpload(files: File[]) {
    if (!files.length || uploadWorkflow.isPending) return;
    uploadWorkflow.mutate(files);
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 py-2">
        <Tooltip content="展开侧栏（⌘\\）" side="right">
          <IconButton
            label="展开侧栏"
            icon={<PanelLeftOpen />}
            tooltip={false}
            onClick={toggleLeftCollapsed}
          />
        </Tooltip>
        <Tooltip content="导入教材" side="right">
          <IconButton
            label="导入教材"
            icon={<Plus />}
            tooltip={false}
            onClick={() => { toggleLeftCollapsed(); setShowUpload(true); }}
          />
        </Tooltip>
        <Tooltip content="教材列表" side="right">
          <IconButton label="教材列表" icon={<BookOpen />} tooltip={false} onClick={toggleLeftCollapsed} />
        </Tooltip>
      </div>
    );
  }

  const hasTextbooks = textbooks && textbooks.length > 0;

  return (
    <>
      <div className="px-3 h-11 border-b border-border-soft flex items-center justify-between shrink-0">
        <h2 className="text-h2 text-text-strong">教材</h2>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<Plus className="size-3.5" />}
            onClick={() => setShowUpload(!showUpload)}
          >
            {showUpload ? "取消" : "添加"}
          </Button>
          <Tooltip content={collapsed ? "展开（⌘\\）" : "折叠（⌘\\）"}>
            <IconButton
              label="折叠"
              tooltip={false}
              size="sm"
              icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
              onClick={toggleLeftCollapsed}
            />
          </Tooltip>
        </div>
      </div>
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {showUpload ? (
          <UploadZone
            onUpload={handleUpload}
            disabled={uploadWorkflow.isPending}
            status={uploadWorkflow.isPending ? "正在解析并生成知识图谱…" : undefined}
          />
        ) : null}

        {isLoading ? (
          <div className="p-3">
            <EmptyState compact title="加载中…" />
          </div>
        ) : !hasTextbooks ? (
          <div className="p-3">
            <EmptyState
              compact
              icon={<BookOpen />}
              title="还没有教材"
              description="点击「添加」按钮导入 PDF / Word / Excel / PPT。"
            />
          </div>
        ) : (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <div className="basis-1/2 min-h-[180px] shrink-0 border-b border-border-soft overflow-hidden">
              <TextbookList
                textbooks={textbooks}
                selectedId={selectedTextbookId}
                onSelect={setSelectedTextbookId}
                height={260}
              />
            </div>
            <div className="basis-1/2 min-h-0 flex flex-col">
              <div className="px-3 py-2 bg-surface-card border-b border-border-soft shrink-0">
                <h3 className="text-meta uppercase tracking-wide text-text-muted font-medium">
                  章节
                </h3>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto">
                <ChapterTree textbookId={selectedTextbookId} />
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function rawIdsFromJob(result: unknown): string[] {
  if (!result || typeof result !== "object") return [];
  const value = (result as { raw_file_ids?: unknown }).raw_file_ids;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
