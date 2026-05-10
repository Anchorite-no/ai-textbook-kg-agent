import type {
  GraphRagQueryRequest,
  GraphRagQueryResponse,
  GraphRagStatus,
  RagIndexRequest,
  RagIndexResponse,
  RagIndexStatus,
  RagQueryRequest,
  RagQueryResponse
} from "@/types/api";
import { request } from "./client";

export async function indexRAG(body: RagIndexRequest): Promise<RagIndexResponse> {
  return request<RagIndexResponse>("/api/rag/index", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}

export async function getRAGStatus(): Promise<RagIndexStatus> {
  return request<RagIndexStatus>("/api/rag/status");
}

export async function queryRAG(question: string, topK = 5, rawFileIds: string[] = []): Promise<RagQueryResponse> {
  const body: RagQueryRequest = { question, top_k: topK, raw_file_ids: rawFileIds };
  return request<RagQueryResponse>("/api/rag/query", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}

export async function getGraphRAGStatus(rawFileIds: string[] = []): Promise<GraphRagStatus> {
  return request<GraphRagStatus>("/api/graphrag/status", {
    query: rawFileIds.length ? { raw_file_ids: rawFileIds.join(",") } : undefined
  });
}

export async function queryGraphRAG(
  question: string,
  topK = 5,
  rawFileIds: string[] = []
): Promise<GraphRagQueryResponse> {
  const body: GraphRagQueryRequest = {
    question,
    top_k: topK,
    raw_file_ids: rawFileIds,
    max_path_depth: 2,
    include_decisions: true
  };
  return request<GraphRagQueryResponse>("/api/graphrag/query", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}
