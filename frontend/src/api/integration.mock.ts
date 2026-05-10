import type {
  DecisionOverrideRequest,
  IntegrationBuildResponse,
  IntegrationResponse,
  TeacherEditApplyResponse,
  TeacherEditListResponse
} from "@/types/api";

export async function getIntegration(_rawFileIds?: string[]): Promise<IntegrationResponse> {
  await new Promise((r) => setTimeout(r, 300));
  return {
    id: "intg_mock_1",
    raw_file_ids: ["raw_mock_a", "raw_mock_b"],
    alignment_id: null,
    decisions: [
      {
        id: "dec_1",
        cluster_id: null,
        action: "merge",
        target_node_ids: ["knode_mock_1", "knode_mock_2"],
        retained_content: "心脏",
        removed_redundancy: "心脏结构",
        reason: "两者指代同一概念，定义高度重叠",
        confidence: 0.95,
        evidence_chunk_ids: [],
        created_at: new Date().toISOString(),
        metadata: {}
      },
      {
        id: "dec_2",
        cluster_id: null,
        action: "keep",
        target_node_ids: ["knode_mock_23", "knode_mock_24"],
        retained_content: null,
        removed_redundancy: null,
        reason: "收缩压与舒张压是血压的不同维度，需独立保留",
        confidence: 0.98,
        evidence_chunk_ids: [],
        created_at: new Date().toISOString(),
        metadata: {}
      }
    ],
    integrated_concepts: [],
    compression_stats: {
      original_char_count: 120000,
      retained_char_count: 35040,
      original_node_count: 120,
      integrated_node_count: 85,
      merged_node_count: 22,
      kept_node_count: 51,
      removed_node_count: 18,
      refined_node_count: 9,
      conflict_count: 1,
      compression_ratio: 0.292,
      target_compression_ratio: 0.30,
      node_reduction_ratio: 0.291,
      evidence_coverage_ratio: 0.96,
      metadata: {}
    },
    generated_at: new Date().toISOString(),
    metadata: {}
  };
}

export async function buildIntegration(_rawFileIds: string[]): Promise<IntegrationBuildResponse> {
  await new Promise((r) => setTimeout(r, 400));
  const integration = await getIntegration();
  return {
    job: {
      id: `job_integration_${Date.now()}`,
      job_type: "integration_build",
      status: "completed",
      progress: 100,
      message: "mock integration built",
      result: {},
      error: null,
      steps: [],
      retryable: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      context_path: null
    },
    integration_output_path: "mock",
    integration
  };
}

export async function overrideDecision(
  _decisionId: string,
  _body: DecisionOverrideRequest
): Promise<TeacherEditApplyResponse> {
  const integration = await getIntegration();
  return {
    edit: {
      id: `edit_${Date.now()}`,
      target_type: "decision",
      target_id: _decisionId,
      operation: "override_decision",
      before: {},
      after: _body,
      reason: _body.reason,
      created_by: "teacher",
      created_at: new Date().toISOString(),
      affected_ids: [_decisionId],
      metadata: {}
    },
    integration,
    message: "mock override"
  };
}

export async function listTeacherEdits(): Promise<TeacherEditListResponse> {
  return { raw_file_ids: ["raw_mock_a", "raw_mock_b"], edits: [], count: 0 };
}
