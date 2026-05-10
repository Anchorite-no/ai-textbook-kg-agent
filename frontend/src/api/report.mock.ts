import type { ReportGenerateRequest, ReportGenerateResponse } from "@/types/api";

export async function generateReport(body: ReportGenerateRequest): Promise<ReportGenerateResponse> {
  const now = new Date().toISOString();
  return {
    id: `report_mock_${Date.now()}`,
    raw_file_ids: body.raw_file_ids ?? [],
    title: body.title ?? "教材知识整合报告",
    markdown: [
      `# ${body.title ?? "教材知识整合报告"}`,
      "",
      `生成时间：${now}`,
      "",
      "## 数据概览",
      "",
      "- mock 报告仅用于离线开发；生产模式会调用后端 `/api/report/generate`。"
    ].join("\n"),
    generated_at: now,
    metadata: {}
  };
}
