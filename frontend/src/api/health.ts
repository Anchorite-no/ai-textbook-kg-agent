import type { HealthResponse } from "@/types/api";
import { request } from "./client";

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export const healthApi = {
  getHealth
};
