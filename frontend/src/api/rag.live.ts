import type {
  RAGIndexRequest,
  RAGIndexResponse,
  RAGIndexStatus,
  RAGQueryRequest,
  RAGQueryResponse
} from "@/types/api";
import { request } from "./client";

export async function indexRAG(body: RAGIndexRequest): Promise<RAGIndexResponse> {
  return request<RAGIndexResponse>("/api/rag/index", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}

export async function getRAGStatus(): Promise<RAGIndexStatus> {
  return request<RAGIndexStatus>("/api/rag/status");
}

export async function queryRAG(question: string, topK = 5): Promise<RAGQueryResponse> {
  const body: RAGQueryRequest = { question, top_k: topK };
  return request<RAGQueryResponse>("/api/rag/query", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}
