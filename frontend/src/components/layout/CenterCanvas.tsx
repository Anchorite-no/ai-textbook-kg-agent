/** 中栏：图谱画布。GraphToolbar + KnowledgeGraph + NodeInspector。 */

import { useEffect, useMemo } from "react";
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
  const searchKeyword = useUIStore((s) => s.searchKeyword);
  const { toggle: toggleFullscreen } = useFullscreen();

  const filtered = useMemo(() => {
    const nodes = data?.nodes ?? [];
    const edges = data?.edges ?? [];
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) return { nodes, edges };
    const kept = new Set(
      nodes
        .filter((node) =>
          `${node.name} ${node.definition ?? ""} ${(node.aliases ?? []).join(" ")}`.toLowerCase().includes(keyword)
        )
        .map((node) => node.id)
    );
    return {
      nodes: nodes.filter((node) => kept.has(node.id)),
      edges: edges.filter((edge) => kept.has(edge.source_node_id) && kept.has(edge.target_node_id))
    };
  }, [data?.edges, data?.nodes, searchKeyword]);

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
        nodeCount={filtered.nodes.length}
        edgeCount={filtered.edges.length}
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
          edges={filtered.edges}
          nodes={filtered.nodes}
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
