import { useQuery } from "@tanstack/react-query";
import { graphApi } from "@/api/graph";
import { useUIStore } from "@/store/uiStore";
import { useRawFileContext } from "@/hooks/useRawFileContext";

export function useGraphQuery() {
  const mode = useUIStore((s) => s.graphMode);
  const topN = useUIStore((s) => s.graphTopN);
  const displayMode = useUIStore((s) => s.graphDisplayMode);
  const { selectedTextbookId, rawFileIds } = useRawFileContext();
  const effectiveTopN = displayMode === "core" ? Math.min(topN, 220) : Math.max(topN, 420);
  return useQuery({
    queryKey: ["graph", mode, displayMode, selectedTextbookId, rawFileIds.join(","), effectiveTopN],
    queryFn: () => graphApi.fetchGraph({
      mode,
      rawFileId: selectedTextbookId,
      rawFileIds,
      topN: effectiveTopN
    }),
    staleTime: 0
  });
}

export function useNodeDetailQuery(nodeId: string | null) {
  return useQuery({
    queryKey: ["graph.node", nodeId],
    queryFn: () => (nodeId ? graphApi.fetchNode(nodeId) : Promise.resolve(null)),
    enabled: nodeId !== null
  });
}
