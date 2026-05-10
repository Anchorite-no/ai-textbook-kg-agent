import type {
  GraphResponse,
  GraphBuildRequest,
  GraphNodeDetailResponse,
  LayeredGraphBuildRequest,
  LayeredGraphResponse
} from "@/types/api";
import { request } from "./client";
import type { GraphPayloadMock } from "./graph.mock";

export interface FetchGraphOptions {
  mode?: "single" | "merged" | "compare";
  rawFileId?: string | null;
  rawFileIds?: string[];
  topN?: number;
}

export async function fetchGraph(options: FetchGraphOptions = {}): Promise<GraphPayloadMock> {
  const mode = options.mode ?? "single";
  const ids = mode === "single"
    ? [options.rawFileId].filter(Boolean) as string[]
    : (options.rawFileIds?.length ? options.rawFileIds : [options.rawFileId].filter(Boolean) as string[]);

  if (ids.length <= 1) {
    const data = await request<GraphResponse>("/api/graph", {
      query: {
        mode: "single",
        raw_file_id: ids[0],
        top_n: options.topN ?? 220
      }
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

  const perGraphTopN = Math.max(30, Math.ceil((options.topN ?? 220) / Math.max(ids.length, 1)));
  const graphs = await Promise.all(
    ids.map((id) =>
      request<GraphResponse>("/api/graph", {
        query: { mode: "single", raw_file_id: id, top_n: perGraphTopN }
      })
    )
  );
  const nodes = graphs.flatMap((graph) => graph.nodes ?? []);
  const edges = graphs.flatMap((graph) => graph.edges ?? []);
  return {
    nodes,
    edges,
    meta: {
      mode,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      textbookIds: graphs.map((graph) => graph.raw_file_id)
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
    force_rebuild: true,
    max_sections: 80,
    max_nodes_per_section: 8,
    use_llm: true
  };
  const res = await request<{ job: { id: string } }>("/api/graph/build", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
  return { job_id: res.job.id };
}

export async function buildLayeredKG(textbookIds: string[]): Promise<{ job_id: string }> {
  if (textbookIds.length === 0) throw new Error("No textbook IDs provided");
  const body: LayeredGraphBuildRequest = {
    raw_file_id: textbookIds[0],
    force_rebuild: false,
    build_missing_concept_graph: true,
    max_sections: 300,
    max_nodes_per_section: 12,
    use_llm: false
  };
  const res = await request<{ job: { id: string } }>("/api/kg/layers/build", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
  return { job_id: res.job.id };
}

export async function getLayeredKG(rawFileId: string): Promise<LayeredGraphResponse> {
  return request<LayeredGraphResponse>("/api/kg/layers", {
    query: { raw_file_id: rawFileId }
  });
}
