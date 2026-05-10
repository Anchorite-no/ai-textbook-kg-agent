/** 整合报告面板。plan 09 §4.6 + plan 16 §11.3。
 *  - Markdown 预览（react-markdown）
 *  - 生成报告按钮
 *  - 下载 / 复制按钮 */

import { FileText, Download, Copy, Sparkles } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button, EmptyState } from "@/components/_kit";
import { cn } from "@/utils/cn";

const MOCK_REPORT = `# 学科知识整合报告

## 概览

- **教材数量**: 2 本
- **原始节点**: 120 个
- **整合后节点**: 85 个
- **压缩率**: 29.2%

## 整合决策

### 合并决策

1. **心脏 ← 心脏结构**
   - 理由：两者指代同一概念，定义高度重叠
   - 置信度：0.95

2. **血压 ← 动脉血压**
   - 理由：血压通常指动脉血压，临床常用术语
   - 置信度：0.92

### 保留决策

1. **收缩压 / 舒张压**
   - 理由：两者是血压的不同维度，需独立保留
   - 置信度：0.98

## 冲突处理

暂无冲突。

---

*报告生成时间：2026-05-10 12:30*
`;

export function ReportPanel() {
  const [report, setReport] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  function handleGenerate() {
    setGenerating(true);
    // TODO: 接入 report API
    setTimeout(() => {
      setReport(MOCK_REPORT);
      setGenerating(false);
    }, 1200);
  }

  function handleCopy() {
    if (!report) return;
    navigator.clipboard.writeText(report);
  }

  function handleDownload() {
    if (!report) return;
    const blob = new Blob([report], { type: "text/markdown" });
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
          description="整合完成后可生成 Markdown 报告。"
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
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<Copy className="size-3" />}
            onClick={handleCopy}
          >
            复制
          </Button>
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<Download className="size-3" />}
            onClick={handleDownload}
          >
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
