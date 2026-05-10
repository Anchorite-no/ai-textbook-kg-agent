import type { TextbookListResponse, TextbookSummary } from "@/types/api";
import { request } from "./client";

export async function listTextbooks(): Promise<TextbookSummary[]> {
  const data = await request<TextbookListResponse>("/api/textbooks");
  return data.textbooks;
}
