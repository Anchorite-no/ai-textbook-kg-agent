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
import { IconButton, StatusDot, Tag, Tooltip } from "@/components/_kit";
import { Button } from "@/components/_kit";
import { useTextbooksQuery } from "@/hooks/useTextbooks";
import { useUIStore } from "@/store/uiStore";

export function TopBar() {
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  const textbooks = useTextbooksQuery();
  const total = textbooks.data?.length ?? 0;
  const chunkSum = textbooks.data?.reduce((sum, t) => sum + t.chunk_count, 0) ?? 0;

  return (
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
        <Button size="sm" variant="ghost" leftIcon={<Play className="size-3.5" />}>
          导入示例
        </Button>
        <Button size="sm" variant="ghost" leftIcon={<Sparkles className="size-3.5" />}>
          建立索引
        </Button>
        <Button size="sm" variant="primary" leftIcon={<FileText className="size-3.5" />}>
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
          <IconButton label="设置" tooltip={false} icon={<Settings />} />
        </Tooltip>
      </div>
    </header>
  );
}
