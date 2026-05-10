/** Textbooks live adapter 完整版。接入 GPT 已建的全部 textbooks 端点。 */

import type {
  TextbookListResponse,
  TextbookSummary,
  TextbookUploadResponse,
  ParsedTextbook
} from "@/types/api";
import { request } from "./client";

export async function listTextbooks(): Promise<TextbookSummary[]> {
  const data = await request<TextbookListResponse>("/api/textbooks");
  return data.textbooks;
}

export async function uploadTextbook(file: File): Promise<TextbookUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<TextbookUploadResponse>("/api/textbooks/upload", {
    method: "POST",
    body: formData
  });
}

export async function uploadTextbookAsync(file: File): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  return request<{ job_id: string }>("/api/textbooks/upload-async", {
    method: "POST",
    body: formData
  });
}

export async function parseTextbook(rawFileId: string): Promise<ParsedTextbook> {
  return request<ParsedTextbook>(`/api/textbooks/${encodeURIComponent(rawFileId)}/parse`, {
    method: "POST"
  });
}

export async function parseTextbookAsync(rawFileId: string): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(`/api/textbooks/${encodeURIComponent(rawFileId)}/parse-async`, {
    method: "POST"
  });
}

export async function getTextbook(rawFileId: string): Promise<ParsedTextbook> {
  return request<ParsedTextbook>(`/api/textbooks/${encodeURIComponent(rawFileId)}`);
}
