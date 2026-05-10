/** 右栏：4 Tab 功能面板。整合 / RAG / 对话 / 报告。 */

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { GitMerge, MessageSquare, Search, FileText } from "lucide-react";
import { useUIStore, type RightTab } from "@/store/uiStore";
import { cn } from "@/utils/cn";
import { IntegrationPanel } from "@/components/integration/IntegrationPanel";
import { RAGPanel } from "@/components/rag/RAGPanel";
import { DialoguePanel } from "@/components/dialogue/DialoguePanel";
import { ReportPanel } from "@/components/report/ReportPanel";
import { NodeDetailCard } from "@/components/graph/NodeDetailCard";
import { RightPanelCollapseButton } from "./RightPanelCollapseButton";

const tabs: Array<{ value: RightTab; label: string; icon: typeof GitMerge }> = [
  { value: "integration", label: "整合", icon: GitMerge },
  { value: "rag", label: "RAG", icon: Search },
  { value: "dialogue", label: "对话", icon: MessageSquare },
  { value: "report", label: "报告", icon: FileText }
];

export function RightPanel() {
  const activeRightTab = useUIStore((s) => s.activeRightTab);
  const setActiveRightTab = useUIStore((s) => s.setActiveRightTab);
  const nodeDetailOpen = useUIStore((s) => s.nodeDetailOpen);
  const selectedNodeId = useUIStore((s) => s.selectedNodeId);
  const closeNodeDetail = useUIStore((s) => s.closeNodeDetail);

  if (nodeDetailOpen && selectedNodeId) {
    return <NodeDetailCard nodeId={selectedNodeId} onClose={closeNodeDetail} />;
  }

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
        <div className="ml-auto flex items-center">
          <RightPanelCollapseButton />
        </div>
      </TabsPrimitive.List>
      <TabsPrimitive.Content
        value="integration"
        className="flex-1 min-h-0 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <IntegrationPanel />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="rag"
        className="flex-1 min-h-0 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <RAGPanel />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="dialogue"
        className="flex-1 min-h-0 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <DialoguePanel />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="report"
        className="flex-1 min-h-0 animate-fade-in-up data-[state=inactive]:hidden"
      >
        <ReportPanel />
      </TabsPrimitive.Content>
    </TabsPrimitive.Root>
  );
}
