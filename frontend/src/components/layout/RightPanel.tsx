/** 右栏：4 Tab 功能面板。当前为骨架；下个 batch 接每个 Tab 的实际内容。 */

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { GitMerge, MessageSquare, Search, FileText } from "lucide-react";
import { EmptyState } from "@/components/_kit";
import { useUIStore, type RightTab } from "@/store/uiStore";
import { cn } from "@/utils/cn";

const tabs: Array<{ value: RightTab; label: string; icon: typeof GitMerge }> = [
  { value: "integration", label: "整合", icon: GitMerge },
  { value: "rag", label: "RAG", icon: Search },
  { value: "dialogue", label: "对话", icon: MessageSquare },
  { value: "report", label: "报告", icon: FileText }
];

export function RightPanel() {
  const activeRightTab = useUIStore((s) => s.activeRightTab);
  const setActiveRightTab = useUIStore((s) => s.setActiveRightTab);

  return (
    <TabsPrimitive.Root
      value={activeRightTab}
      onValueChange={(v) => setActiveRightTab(v as RightTab)}
      className="flex flex-col flex-1 min-h-0"
      activationMode="manual"
    >
      <TabsPrimitive.List
        className="flex h-10 px-2 border-b border-border-soft bg-surface-card shrink-0"
        aria-label="功能面板"
      >
        {tabs.map(({ value, label, icon: Icon }) => (
          <TabsPrimitive.Trigger
            key={value}
            value={value}
            className={cn(
              "relative inline-flex items-center gap-1.5 px-3 text-meta font-medium",
              "text-text-muted transition-colors duration-micro ease-standard",
              "hover:text-text-default focus-visible:outline-none focus-visible:text-text-default",
              "data-[state=active]:text-brand-700"
            )}
          >
            <Icon className="size-3.5" />
            {label}
            <span
              aria-hidden
              className={cn(
                "absolute bottom-0 left-2 right-2 h-0.5 rounded-pill bg-brand-500 origin-center",
                "scale-x-0 transition-transform duration-fast ease-standard",
                "data-[active=true]:scale-x-100"
              )}
              data-active={activeRightTab === value}
            />
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      <TabsPrimitive.Content
        value="integration"
        className="scroll-region p-4 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <EmptyState
          icon={<GitMerge />}
          title="整合面板"
          description="完成图谱构建后这里会显示压缩比、决策列表与冲突。"
        />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="rag"
        className="scroll-region p-4 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <EmptyState
          icon={<Search />}
          title="RAG 问答"
          description="先建立索引，再在这里输入问题查看回答与引用。"
        />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="dialogue"
        className="scroll-region p-4 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <EmptyState
          icon={<MessageSquare />}
          title="教师对话"
          description="可以问「为什么删除某节点？」或要求保留 / 拆分整合方案。"
        />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="report"
        className="scroll-region p-4 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <EmptyState
          icon={<FileText />}
          title="整合报告"
          description="整合完成后可生成 Markdown 报告。"
        />
      </TabsPrimitive.Content>
    </TabsPrimitive.Root>
  );
}
