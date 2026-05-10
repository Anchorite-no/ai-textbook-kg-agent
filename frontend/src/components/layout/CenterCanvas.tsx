/** 中栏：图谱画布。当前为骨架；下个 batch 接 GraphToolbar + KnowledgeGraph。 */

import { Activity, Maximize2 } from "lucide-react";
import { EmptyState, IconButton, Tag, Tooltip } from "@/components/_kit";
import { useUIStore } from "@/store/uiStore";

export function CenterCanvas() {
  const graphMode = useUIStore((s) => s.graphMode);

  return (
    <>
      <div className="h-12 px-4 border-b border-border-soft flex items-center gap-3 bg-surface-card/80 backdrop-blur-sm shrink-0">
        <Tag variant="brand" size="md">
          {graphMode === "single" ? "单本图谱" : graphMode === "merged" ? "整合图谱" : "整合前后对比"}
        </Tag>
        <span className="text-meta text-text-muted tabular">0 节点 · 0 边</span>
        <div className="ml-auto flex items-center gap-1">
          <Tooltip content="重置视图（⌘0）">
            <IconButton label="重置视图" tooltip={false} icon={<Activity />} />
          </Tooltip>
          <Tooltip content="全屏">
            <IconButton label="全屏" tooltip={false} icon={<Maximize2 />} />
          </Tooltip>
        </div>
      </div>
      <div className="scroll-region flex items-center justify-center grid-bg">
        <EmptyState
          title="导入教材并构建图谱后显示"
          description="工作台中央保留给力导向图谱。"
        />
      </div>
    </>
  );
}
