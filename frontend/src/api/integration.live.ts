import type {
  DecisionOverrideRequest,
  IntegrationBuildResponse,
  IntegrationResponse,
  TeacherEditApplyResponse,
  TeacherEditListResponse
} from "@/types/api";
import { request } from "./client";

export async function getIntegration(rawFileIds?: string[]): Promise<IntegrationResponse> {
  return request<IntegrationResponse>("/api/integration", {
    query: rawFileIds?.length ? { raw_file_ids: rawFileIds.join(",") } : undefined
  });
}

export async function buildIntegration(rawFileIds: string[]): Promise<IntegrationBuildResponse> {
  return request<IntegrationBuildResponse>("/api/integration/build", {
    method: "POST",
    body: {
      raw_file_ids: rawFileIds,
      force_rebuild: false,
      target_compression_ratio: 0.3,
      alignment_min_confidence: 0.62,
      include_keep_decisions: true
    }
  });
}

export async function overrideDecision(
  decisionId: string,
  body: DecisionOverrideRequest
): Promise<TeacherEditApplyResponse> {
  return request<TeacherEditApplyResponse>(
    `/api/integration/decisions/${encodeURIComponent(decisionId)}/override`,
    {
      method: "POST",
      body: body as unknown as Record<string, unknown>
    }
  );
}

export async function listTeacherEdits(rawFileIds: string[] = []): Promise<TeacherEditListResponse> {
  return request<TeacherEditListResponse>("/api/teacher-edits", {
    query: rawFileIds.length ? { raw_file_ids: rawFileIds.join(",") } : undefined
  });
}
