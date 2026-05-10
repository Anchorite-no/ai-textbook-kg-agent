import type {
  GraphResponse,
  KnowledgeNode,
  KnowledgeEdge,
  GraphBuildRequest,
  GraphNodeDetailResponse
} from "@/types/api";
import { request } from "./client";
import type { GraphPayloadMock } from "./graph.mock";

export async function fetchGraph(
  mode: "single" | "merged" | "compare" = "single"
): Promise<GraphPayloadMock> {
  const data = await request<GraphResponse>("/api/graph", {
    query: { mode: "single" }
  });
  const nodes = data.nodes ?? [];
  const edges = data.edges ?? [];
  return {
    nodes,
    edges,
    meta: {
      mode,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      textbookIds: data.raw_file_id ? [data.raw_file_id] : []
    }
  };
}

export async function fetchNode(nodeId: string): Promise<GraphNodeDetailResponse | null> {
  return request<GraphNodeDetailResponse>(`/api/graph/nodes/${encodeURIComponent(nodeId)}`);
}

export async function buildGraph(textbookIds: string[]): Promise<{ job_id: string }> {
  if (textbookIds.length === 0) throw new Error("No textbook IDs provided");
  const body: GraphBuildRequest = {
    raw_file_id: textbookIds[0],
    force_rebuild: false,
    max_sections: 100,
    max_nodes_per_section: 50,
    use_llm: true
  };
  return request<{ job_id: string }>("/api/graph/build", {
    method: "POST",
    body
  });
}

export async function buildLayeredKG(textbookIds: string[]): Promise<{ job_id: string }> {
  if (textbookIds.length === 0) throw new Error("No textbook IDs provided");
  return request<{ job_id: string }>("/api/kg/layers/build", {
    method: "POST",
    body: {
      raw_file_id: textbookIds[0],
      force_rebuild: false,
      max_layers: 3
    }
  });
}

export async function getLayeredKG(): Promise<unknown> {
  return request<unknown>("/api/kg/layers");
}
