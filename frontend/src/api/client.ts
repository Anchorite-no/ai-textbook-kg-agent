import type {
  HealthResponse,
  JobRecord,
  ParsedTextbook,
  TextbookListResponse,
  TextbookUploadResponse
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health");
}

export function importConvertedTextbook(textbookTitle?: string): Promise<TextbookUploadResponse> {
  const form = new FormData();
  if (textbookTitle) {
    form.append("textbook_title", textbookTitle);
  }
  return requestJson<TextbookUploadResponse>("/api/textbooks/upload", {
    method: "POST",
    body: form
  });
}

export function getJob(jobId: string): Promise<JobRecord> {
  return requestJson<JobRecord>(`/api/jobs/${jobId}`);
}

export function listTextbooks(): Promise<TextbookListResponse> {
  return requestJson<TextbookListResponse>("/api/textbooks");
}

export function getTextbook(rawFileId: string): Promise<ParsedTextbook> {
  return requestJson<ParsedTextbook>(`/api/textbooks/${rawFileId}`);
}
