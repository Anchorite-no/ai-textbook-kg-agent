import type {
  AlignmentBuildResponse,
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
  const ids = Array.from(new Set(rawFileIds)).sort();
  if (ids.length < 2) throw new Error("至少需要两本教材才能构建跨教材整合。");
  await request<AlignmentBuildResponse>("/api/alignment/build", {
    method: "POST",
    body: {
      raw_file_ids: ids,
      force_rebuild: false,
      min_confidence: 0.62,
      include_singletons: false,
      max_nodes: 4000
    }
  });
  return request<IntegrationBuildResponse>("/api/integration/build", {
    method: "POST",
    body: {
      raw_file_ids: ids,
      force_rebuild: false,
      target_compression_ratio: 0.3,
      alignment_min_confidence: 0.62,
      include_keep_decisions: true,
      max_nodes: 4000
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
