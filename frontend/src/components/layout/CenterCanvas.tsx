/** 中栏：图谱画布。GraphToolbar + KnowledgeGraph + NodeInspector。 */

import { useEffect } from "react";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { KnowledgeGraph } from "@/components/graph/KnowledgeGraph";
import { EdgeLegend } from "@/components/graph/EdgeLegend";
import { useGraphQuery } from "@/hooks/useGraph";
import { useUIStore } from "@/store/uiStore";
import { useFullscreen } from "@/hooks/useFullscreen";

export function CenterCanvas() {
  const { data, isLoading, isFetching, error, refetch } = useGraphQuery();
  const selectedNodeId = useUIStore((s) => s.selectedNodeId);
  const setSelectedNodeId = useUIStore((s) => s.setSelectedNodeId);
  const { toggle: toggleFullscreen } = useFullscreen();

  // ESC 关闭 NodeInspector
  useEffect(() => {
    if (!selectedNodeId) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setSelectedNodeId(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedNodeId, setSelectedNodeId]);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <GraphToolbar
        nodeCount={data?.meta.nodeCount ?? 0}
        edgeCount={data?.meta.edgeCount ?? 0}
        fetching={isFetching}
        onRefresh={() => refetch()}
        onResetView={() => {
          // 触发 zoom reset
          const event = new CustomEvent("graph:reset");
          window.dispatchEvent(event);
        }}
        onFullscreen={toggleFullscreen}
      />
      <div className="flex-1 relative flex flex-col min-h-0">
        <KnowledgeGraph
          nodes={data?.nodes}
          edges={data?.edges}
          loading={isLoading}
          error={error instanceof Error ? error.message : null}
          onRetry={() => refetch()}
          selectedNodeId={selectedNodeId}
          onSelect={setSelectedNodeId}
        />
        <EdgeLegend />
      </div>
    </div>
  );
}
