import type {
  DialogueHistoryResponse,
  DialogueMessageRequest,
  DialogueMessageResponse
} from "@/types/api";
import { request } from "./client";

export async function getHistory(rawFileIds?: string[]): Promise<DialogueHistoryResponse> {
  return request<DialogueHistoryResponse>("/api/dialogue/messages", {
    query: rawFileIds?.length ? { raw_file_ids: rawFileIds.join(",") } : undefined
  });
}

export async function sendMessage(body: DialogueMessageRequest): Promise<DialogueMessageResponse> {
  return request<DialogueMessageResponse>("/api/dialogue/messages", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}
