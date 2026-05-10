/** 顶部状态栏。plan 09 §3.2、plan 16 §11.1。
 *  - 左：Logo + 项目名 + 数据集名
 *  - 中：状态徽章组（教材数 / chunks / 任务）
 *  - 右：操作组 + 主题切换 + 设置 */

import {
  BookOpen,
  Database,
  FileText,
  Moon,
  Play,
  Settings,
  Sparkles,
  Sun
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { IconButton, StatusDot, Tag, Tooltip } from "@/components/_kit";
import { Button } from "@/components/_kit";
import { datasetsApi } from "@/api/datasets";
import { jobsApi } from "@/api/jobs";
import { ragApi } from "@/api/rag";
import { toastStore } from "@/components/layout/ToastViewport";
import { SettingsDialog } from "@/components/layout/SettingsDialog";
import { useSevenBooksDatasetQuery, useTextbooksQuery } from "@/hooks/useTextbooks";
import { useUIStore } from "@/store/uiStore";

export function TopBar() {
  const queryClient = useQueryClient();
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);
  const setSelectedTextbookId = useUIStore((s) => s.setSelectedTextbookId);
  const setWorkspaceRawFileIds = useUIStore((s) => s.setWorkspaceRawFileIds);
  const setActiveRightTab = useUIStore((s) => s.setActiveRightTab);
  const requestReportGenerate = useUIStore((s) => s.requestReportGenerate);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const textbooks = useTextbooksQuery();
  const dataset = useSevenBooksDatasetQuery();
  const total = textbooks.data?.length ?? 0;
  const chunkSum = textbooks.data?.reduce((sum, t) => sum + t.chunk_count, 0) ?? 0;
  const contextIds = dataset.data?.raw_file_ids?.length
    ? dataset.data.raw_file_ids
    : textbooks.data?.map((item) => item.raw_file_id) ?? [];

  const prepareDataset = useMutation({
    mutationFn: async () => {
      const currentRawFileIds = dataset.data?.raw_file_ids ?? [];
      if (dataset.data?.status === "ready" && currentRawFileIds.length > 0) {
        return { rawFileIds: currentRawFileIds, prepared: false };
      }
      const accepted = await datasetsApi.prepareSevenBooks({
        force_rebuild: false,
        build_graph: true,
        build_layered_graph: true,
        build_rag: true,
        build_alignment: true,
        build_integration: true,
        use_llm: false
      });
      const job = await jobsApi.waitForJob(accepted.job.id, 300_000);
      const rawFileIds = rawIdsFromJob(job.result) || accepted.dataset.raw_file_ids || [];
      return { rawFileIds, prepared: true };
    },
    onSuccess: async ({ rawFileIds, prepared }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dataset", "seven-books"] }),
        queryClient.invalidateQueries({ queryKey: ["textbooks"] }),
        queryClient.invalidateQueries({ queryKey: ["graph"] }),
        queryClient.invalidateQueries({ queryKey: ["integration"] }),
        queryClient.invalidateQueries({ queryKey: ["rag"] })
      ]);
      if (rawFileIds.length) {
        setWorkspaceRawFileIds(rawFileIds);
        setSelectedTextbookId(rawFileIds[0]);
      }
      toastStore.push({
        tone: "success",
        title: prepared ? "七本书数据集已准备" : "七本书数据集已载入",
        description: `${rawFileIds.length} 本教材已作为当前工作上下文`
      });
    }
  });

  const indexRag = useMutation({
    mutationFn: () => ragApi.indexRAG({ raw_file_ids: contextIds, force_rebuild: true }),
    onSuccess: async (res) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["rag"] }),
        queryClient.invalidateQueries({ queryKey: ["graph"] })
      ]);
      toastStore.push({
        tone: "success",
        title: "RAG 索引已建立",
        description: `${res.status.chunk_count.toLocaleString()} 个 chunk 已进入证据索引`
      });
    }
  });

  function handleGenerateReport() {
    setActiveRightTab("report");
    requestAnimationFrame(() => requestReportGenerate());
  }

  return (
    <>
      <header
        className="flex items-center px-3 gap-3 border-b border-border-soft bg-surface-card/95 backdrop-blur-sm"
        style={{ height: "var(--topbar-height)" }}
      >
      {/* 左：logo */}
      <div className="flex items-center gap-2 min-w-0">
        <span
          className="inline-flex items-center justify-center size-7 rounded-control bg-brand-500 text-text-inverse shrink-0"
          aria-hidden
        >
          <BookOpen className="size-4" />
        </span>
        <div className="flex items-baseline gap-2 min-w-0">
          <h1 className="text-h2 text-text-strong truncate">学科知识整合智能体</h1>
        </div>
      </div>

      {/* 分隔 */}
      <span className="h-5 w-px bg-border-soft shrink-0" aria-hidden />

      {/* 中：状态徽章组 */}
      <div className="flex items-center gap-2 min-w-0">
        <Tooltip content={`已加载 ${total} 本教材`}>
          <Tag variant="neutral" leadingIcon={<BookOpen />}>
            <span className="tabular">{total}</span>
            <span className="text-text-muted ml-1">本</span>
          </Tag>
        </Tooltip>
        <Tooltip content={`已索引 ${chunkSum.toLocaleString()} 条 chunk`}>
          <Tag variant="neutral" leadingIcon={<Database />}>
            <span className="tabular">{chunkSum.toLocaleString()}</span>
            <span className="text-text-muted ml-1">chunks</span>
          </Tag>
        </Tooltip>
        <Tooltip content="当前任务">
          <Tag variant="neutral">
            <StatusDot status={textbooks.isFetching ? "running" : "pending"} size="xs" />
            <span className="ml-1.5">
              {textbooks.isFetching ? "同步教材列表" : "空闲"}
            </span>
          </Tag>
        </Tooltip>
      </div>

      {/* 右：操作组 */}
      <div className="ml-auto flex items-center gap-1">
        <Button
          size="sm"
          variant="ghost"
          leftIcon={<Play className="size-3.5" />}
          loading={prepareDataset.isPending}
          onClick={() => prepareDataset.mutate()}
        >
          {dataset.data?.status === "ready" ? "载入示例" : "导入示例"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          leftIcon={<Sparkles className="size-3.5" />}
          loading={indexRag.isPending}
          disabled={contextIds.length === 0}
          onClick={() => indexRag.mutate()}
        >
          建立索引
        </Button>
        <Button
          size="sm"
          variant="primary"
          leftIcon={<FileText className="size-3.5" />}
          onClick={handleGenerateReport}
        >
          生成报告
        </Button>
        <span className="h-5 w-px bg-border-soft mx-1" aria-hidden />
        <Tooltip content={theme === "light" ? "切到暗色" : "切到亮色"}>
          <IconButton
            label="切换主题"
            tooltip={false}
            icon={theme === "light" ? <Moon /> : <Sun />}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          />
        </Tooltip>
        <Tooltip content="设置">
          <IconButton
            label="设置"
            tooltip={false}
            icon={<Settings />}
            onClick={() => setSettingsOpen(true)}
          />
        </Tooltip>
      </div>
      </header>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </>
  );
}

function rawIdsFromJob(result: unknown): string[] | null {
  if (!result || typeof result !== "object") return null;
  const value = (result as { raw_file_ids?: unknown }).raw_file_ids;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : null;
}
