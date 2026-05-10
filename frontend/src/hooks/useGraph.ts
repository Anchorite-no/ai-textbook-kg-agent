import { useQuery } from "@tanstack/react-query";
import { graphApi } from "@/api/graph";
import { useUIStore } from "@/store/uiStore";
import { useRawFileContext } from "@/hooks/useRawFileContext";

export function useGraphQuery() {
  const mode = useUIStore((s) => s.graphMode);
  const topN = useUIStore((s) => s.graphTopN);
  const { selectedTextbookId, rawFileIds } = useRawFileContext();
  return useQuery({
    queryKey: ["graph", mode, selectedTextbookId, rawFileIds.join(","), topN],
    queryFn: () => graphApi.fetchGraph({
      mode,
      rawFileId: selectedTextbookId,
      rawFileIds,
      topN
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
