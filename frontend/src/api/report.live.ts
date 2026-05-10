import type { ReportGenerateRequest, ReportGenerateResponse } from "@/types/api";
import { request } from "./client";

export async function generateReport(body: ReportGenerateRequest): Promise<ReportGenerateResponse> {
  return request<ReportGenerateResponse>("/api/report/generate", {
    method: "POST",
    body: body as unknown as Record<string, unknown>
  });
}
