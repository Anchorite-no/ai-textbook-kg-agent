import { useQuery } from "@tanstack/react-query";
import { graphApi } from "@/api/graph";
import { useUIStore } from "@/store/uiStore";

export function useGraphQuery() {
  const mode = useUIStore((s) => s.graphMode);
  return useQuery({
    queryKey: ["graph", mode],
    queryFn: () => graphApi.fetchGraph(mode),
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
