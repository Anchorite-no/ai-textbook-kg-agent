import type { IntegrationResponse } from "@/types/api";

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
      original_node_count: 120,
      integrated_node_count: 85,
      compression_ratio: 0.292,
      target_compression_ratio: 0.30,
      original_edge_count: 200,
      integrated_edge_count: 150
    },
    generated_at: new Date().toISOString(),
    metadata: {}
  };
}

export async function buildIntegration(_rawFileIds: string[]): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 400));
  return { job_id: `job_integration_${Date.now()}` };
}
