import { FileText, Download, Copy, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { Button, EmptyState } from "@/components/_kit";
import { integrationApi } from "@/api/integration";
import { ragApi } from "@/api/rag";
import { reportApi } from "@/api/report";
import { toastStore } from "@/components/layout/ToastViewport";
import { useRawFileContext } from "@/hooks/useRawFileContext";
import { useUIStore } from "@/store/uiStore";
import { cn } from "@/utils/cn";

export function ReportPanel() {
  const { rawFileIds, textbooks, dataset } = useRawFileContext();
  const reportGenerateTick = useUIStore((s) => s.reportGenerateTick);
  const [report, setReport] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const integration = useQuery({
    queryKey: ["integration", rawFileIds.join(","), "report"],
    queryFn: () => integrationApi.getIntegration(rawFileIds),
    enabled: rawFileIds.length >= 2,
    retry: false
  });
  const ragStatus = useQuery({
    queryKey: ["rag", "status"],
    queryFn: ragApi.getRAGStatus,
    retry: false
  });
  const graphRagStatus = useQuery({
    queryKey: ["graphrag", "status", rawFileIds.join(",")],
    queryFn: () => ragApi.getGraphRAGStatus(rawFileIds),
    enabled: rawFileIds.length > 0,
    retry: false
  });

  useEffect(() => {
    if (reportGenerateTick > 0) handleGenerate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportGenerateTick]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const generated = await reportApi.generateReport({
        raw_file_ids: rawFileIds,
        title: `${dataset?.title ?? "当前教材集合"}整合报告`,
        include_dataset_metrics: true,
        include_graph_metrics: true,
        include_integration: true
      });
      setReport(generated.markdown);
      toastStore.push({ tone: "success", title: "报告已生成", description: "内容来自后端真实教材、索引和整合结果" });
    } catch {
      const next = buildReport({
        datasetTitle: dataset?.title ?? "当前教材集合",
        textbooks,
        rawFileIds,
        integration: integration.data,
        ragStatus: ragStatus.data,
        graphRagStatus: graphRagStatus.data
      });
      setReport(next);
      toastStore.push({ tone: "warning", title: "后端报告接口暂不可用", description: "已使用当前真实接口缓存生成本地摘要" });
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy() {
    if (!report) return;
    await navigator.clipboard.writeText(report);
    toastStore.push({ tone: "success", title: "报告已复制" });
  }

  function handleDownload() {
    if (!report) return;
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `整合报告_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!report) {
    return (
      <div className="flex flex-col h-full items-center justify-center p-4">
        <EmptyState
          icon={<FileText />}
          title="整合报告"
          description="基于当前教材、RAG 索引和跨教材整合结果生成 Markdown 报告。"
          action={
            <Button
              variant="primary"
              leftIcon={<Sparkles className="size-3.5" />}
              onClick={handleGenerate}
              loading={generating}
            >
              生成报告
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-border-soft flex items-center justify-between">
        <h3 className="text-h2 text-text-strong">整合报告</h3>
        <div className="flex items-center gap-1">
          <Button size="sm" variant="ghost" leftIcon={<Sparkles className="size-3" />} onClick={handleGenerate} loading={generating}>
            重生成
          </Button>
          <Button size="sm" variant="ghost" leftIcon={<Copy className="size-3" />} onClick={handleCopy}>
            复制
          </Button>
          <Button size="sm" variant="ghost" leftIcon={<Download className="size-3" />} onClick={handleDownload}>
            下载
          </Button>
        </div>
      </div>
      <div className="flex-1 scroll-region p-4">
        <div
          className={cn(
            "prose prose-sm max-w-none",
            "prose-headings:text-text-strong prose-p:text-text-default",
            "prose-strong:text-text-strong prose-code:text-brand-700",
            "prose-ul:text-text-default prose-ol:text-text-default"
          )}
        >
          <ReactMarkdown>{report}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

function buildReport(input: {
  datasetTitle: string;
  textbooks: Array<{ title: string; raw_file_id: string; chunk_count: number; section_count: number }>;
  rawFileIds: string[];
  integration: Awaited<ReturnType<typeof integrationApi.getIntegration>> | undefined;
  ragStatus: Awaited<ReturnType<typeof ragApi.getRAGStatus>> | undefined;
  graphRagStatus: Awaited<ReturnType<typeof ragApi.getGraphRAGStatus>> | undefined;
}): string {
  const stats = input.integration?.compression_stats;
  const decisions = input.integration?.decisions ?? [];
  const byAction = (action: string) => decisions.filter((decision) => decision.action === action);
  const topDecisions = decisions.slice(0, 12);
  return [
    `# ${input.datasetTitle}整合报告`,
    "",
    `生成时间：${new Date().toLocaleString("zh-CN")}`,
    "",
    "## 数据概览",
    "",
    `- 教材数量：${input.rawFileIds.length} 本`,
    `- 章节数量：${input.textbooks.reduce((sum, item) => sum + item.section_count, 0).toLocaleString()}`,
    `- Chunk 数量：${input.textbooks.reduce((sum, item) => sum + item.chunk_count, 0).toLocaleString()}`,
    `- RAG 索引：${input.ragStatus?.status ?? "unknown"}，${(input.ragStatus?.chunk_count ?? 0).toLocaleString()} chunks`,
    `- GraphRAG：${input.graphRagStatus?.status ?? "unknown"}，${input.graphRagStatus?.node_count ?? 0} 节点 / ${input.graphRagStatus?.edge_count ?? 0} 边`,
    "",
    "## 教材清单",
    "",
    ...input.textbooks.map((book, index) => `${index + 1}. ${book.title}（${book.section_count} 章节，${book.chunk_count} chunks）`),
    "",
    "## 整合压缩",
    "",
    stats
      ? `- 压缩率：${(stats.compression_ratio * 100).toFixed(1)}%（目标 ${(stats.target_compression_ratio * 100).toFixed(0)}%）`
      : "- 尚未读取到整合压缩结果。",
    stats ? `- 节点：${stats.original_node_count} -> ${stats.integrated_node_count}` : "",
    stats ? `- 字符：${stats.original_char_count.toLocaleString()} -> ${stats.retained_char_count.toLocaleString()}` : "",
    stats ? `- 证据覆盖率：${(stats.evidence_coverage_ratio * 100).toFixed(1)}%` : "",
    "",
    "## 决策分布",
    "",
    `- 合并：${byAction("merge").length}`,
    `- 保留：${byAction("keep").length}`,
    `- 移除：${byAction("remove").length}`,
    `- 细化：${byAction("refine").length}`,
    `- 冲突：${byAction("conflict").length}`,
    "",
    "## 代表性整合决策",
    "",
    ...(topDecisions.length
      ? topDecisions.map((decision, index) => `${index + 1}. **${decision.action}**：${decision.reason}`)
      : ["暂无可展示决策。"]),
    "",
    "## 证据链说明",
    "",
    "所有教材结构、知识节点、RAG 引用和整合决策均保留 `source_locator`，可回溯到原始教材页码、章节、chunk 或办公文档位置。"
  ].filter(Boolean).join("\n");
}
