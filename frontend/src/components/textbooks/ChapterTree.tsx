/** 章节树。plan 16 §11.2。
 *  - 折叠树（Radix Collapsible）
 *  - 点击章节 → 跳转到对应 chunk / 节点
 *  - 当前为占位实现，等后端暴露 sections 后接入 */

import { ChevronRight, FileText } from "lucide-react";
import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import { cn } from "@/utils/cn";
import { EmptyState } from "@/components/_kit";

export interface ChapterTreeProps {
  textbookId: string | null;
}

interface Chapter {
  id: string;
  title: string;
  level: number;
  children: Chapter[];
}

// Mock 数据，后续从 API 读取
const MOCK_CHAPTERS: Chapter[] = [
  {
    id: "ch1",
    title: "第一章 循环系统概述",
    level: 1,
    children: [
      { id: "ch1.1", title: "1.1 心脏结构", level: 2, children: [] },
      { id: "ch1.2", title: "1.2 血管系统", level: 2, children: [] }
    ]
  },
  {
    id: "ch2",
    title: "第二章 心脏生理",
    level: 1,
    children: [
      { id: "ch2.1", title: "2.1 心动周期", level: 2, children: [] },
      { id: "ch2.2", title: "2.2 心输出量", level: 2, children: [] }
    ]
  },
  {
    id: "ch3",
    title: "第三章 血压调节",
    level: 1,
    children: []
  }
];

export function ChapterTree({ textbookId }: ChapterTreeProps) {
  if (!textbookId) {
    return (
      <div className="p-3">
        <EmptyState
          compact
          icon={<FileText />}
          title="选择教材查看章节"
          description="点击左侧教材列表中的任意一本。"
        />
      </div>
    );
  }

  return (
    <div className="p-2">
      <div className="flex flex-col gap-0.5">
        {MOCK_CHAPTERS.map((chapter) => (
          <ChapterNode key={chapter.id} chapter={chapter} />
        ))}
      </div>
    </div>
  );
}

function ChapterNode({ chapter }: { chapter: Chapter }) {
  const [open, setOpen] = useState(false);
  const hasChildren = chapter.children.length > 0;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <button
          className={cn(
            "w-full flex items-center gap-1.5 px-2 py-1.5 rounded-control text-left",
            "text-meta text-text-default hover:bg-surface-input transition-colors duration-micro",
            "group"
          )}
          style={{ paddingLeft: `${(chapter.level - 1) * 12 + 8}px` }}
        >
          {hasChildren ? (
            <ChevronRight
              className={cn(
                "size-3 text-text-subtle transition-transform duration-micro shrink-0",
                open && "rotate-90"
              )}
              aria-hidden
            />
          ) : (
            <span className="size-3 shrink-0" aria-hidden />
          )}
          <span className="truncate flex-1">{chapter.title}</span>
        </button>
      </Collapsible.Trigger>
      {hasChildren ? (
        <Collapsible.Content className="flex flex-col gap-0.5">
          {chapter.children.map((child) => (
            <ChapterNode key={child.id} chapter={child} />
          ))}
        </Collapsible.Content>
      ) : null}
    </Collapsible.Root>
  );
}
