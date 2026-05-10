import type { IntegrationResponse } from "@/types/api";
import { request } from "./client";

export async function getIntegration(rawFileIds?: string[]): Promise<IntegrationResponse> {
  return request<IntegrationResponse>("/api/integration", {
    query: rawFileIds?.length ? { raw_file_ids: rawFileIds.join(",") } : undefined
  });
}

export async function buildIntegration(rawFileIds: string[]): Promise<unknown> {
  return request("/api/integration/build", {
    method: "POST",
    body: { raw_file_ids: rawFileIds }
  });
}
