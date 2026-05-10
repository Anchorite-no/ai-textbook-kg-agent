/** 与 plan 17 §3.4 对齐：前端类型层
 *
 * 1. 业务实体一律从 ./api.generated re-export，不要手写。
 * 2. UI 自有类型（不进后端、不进 OpenAPI）写在本文件 §B。
 * 3. 后端尚未建的实体（图谱、整合决策、RAG 等）暂时在 §C 手写存根，
 *    一旦 GPT 建好对应 endpoint，立即删除手写存根、改为从 generated re-export。
 */

import type { components } from "./api.generated";

export type Schemas = components["schemas"];

/* ---------- §A 已在 generated 的契约实体 ---------- */
export type SourceLocator = Schemas["SourceLocator"];
export type RawFile = Schemas["RawFile"];
export type DocumentElement = Schemas["DocumentElement"];
export type DocumentElementType = Schemas["DocumentElementType"];
export type Section = Schemas["Section"];
export type SectionType = Schemas["SectionType"];
export type Chunk = Schemas["Chunk"];
export type ParsedTextbook = Schemas["ParsedTextbook"];

export type JobRecord = Schemas["JobRecord"];
export type JobType = Schemas["JobType"];
export type JobStatus = Schemas["JobStatus"];

export type HealthResponse = Schemas["HealthResponse"];
export type TextbookSummary = Schemas["TextbookSummary"];
export type TextbookListResponse = Schemas["TextbookListResponse"];
export type TextbookUploadResponse = Schemas["TextbookUploadResponse"];
export type TextbookUploadError = Schemas["TextbookUploadError"];
export type TextbookBatchUploadResponse = Schemas["TextbookBatchUploadResponse"];
export type SampleBookSummary = Schemas["SampleBookSummary"];
export type SampleDatasetResponse = Schemas["SampleDatasetResponse"];
export type SampleDatasetPrepareRequest = Schemas["SampleDatasetPrepareRequest"];
export type SampleDatasetPrepareResponse = Schemas["SampleDatasetPrepareResponse"];
export type OrganizeWorkflowAcceptedResponse = Schemas["OrganizeWorkflowAcceptedResponse"];

// Phase 3：图谱（GPT 已建好）
export type KnowledgeNode = Schemas["KnowledgeNode"];
export type KnowledgeNodeType = Schemas["KnowledgeNodeType"];
export type KnowledgeEdge = Schemas["KnowledgeEdge"];
export type KnowledgeRelationType = Schemas["KnowledgeRelationType"];
export type GraphResponse = Schemas["GraphResponse"];
export type GraphBuildRequest = Schemas["GraphBuildRequest"];
export type GraphBuildResponse = Schemas["GraphBuildResponse"];
export type GraphNodeDetailResponse = Schemas["GraphNodeDetailResponse"];

export type ApiErrorResponse = Schemas["ApiErrorResponse"];

/* ---------- §B UI 自有类型（不进 backend）---------- */

export type StatusVariant = "pending" | "running" | "success" | "warning" | "error";

/** 文件上传 UI 状态（前端组合后端 JobStatus + 本地阶段） */
export interface UploadProgressUi {
  fileId: string;
  filename: string;
  format: string;
  phase: "queued" | "uploading" | "parsing" | "done" | "error";
  percent: number;
  errorMessage?: string;
}

/** 图谱渲染层节点（D3 计算位置后） */
export interface GraphRenderNode {
  id: string;
  label: string;
  bookId: string;
  bookHue: number;
  confidence: number;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  selected: boolean;
}

export interface GraphRenderEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface GraphPayload {
  nodes: GraphRenderNode[];
  edges: GraphRenderEdge[];
  meta: {
    mode: "single" | "merged" | "compare";
    nodeCount: number;
    edgeCount: number;
  };
}

/* ---------- §C 后端已建但 schema 未在 openapi.snapshot.json 的实体 ---------- */

// ── RAG ──

export interface RAGIndexRequest {
  raw_file_ids: string[];
  force_rebuild?: boolean;
  max_chunks?: number | null;
}

export interface RAGIndexStatus {
  status: "empty" | "ready";
  textbook_count: number;
  chunk_count: number;
  raw_file_ids: string[];
  index_path: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown>;
}

export interface RAGIndexResponse {
  job: JobRecord;
  status: RAGIndexStatus;
}

export interface RAGQueryRequest {
  question: string;
  top_k?: number;
  raw_file_ids?: string[];
}

export interface RAGCitation {
  chunk_id: string;
  raw_file_id: string;
  textbook: string;
  chapter: string | null;
  source_locator: SourceLocator;
  relevance_score: number;
  quote: string;
  metadata: Record<string, unknown>;
}

export interface RAGQueryResponse {
  question: string;
  answer: string;
  citations: RAGCitation[];
  source_chunks: Chunk[];
  metadata: Record<string, unknown>;
}

// ── Integration ──

export type IntegrationAction = "merge" | "keep" | "remove" | "refine" | "conflict";

export interface IntegrationDecision {
  id: string;
  cluster_id: string | null;
  action: IntegrationAction;
  target_node_ids: string[];
  retained_content: string | null;
  removed_redundancy: string | null;
  reason: string;
  confidence: number;
  evidence_chunk_ids: string[];
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface CompressionStats {
  original_node_count: number;
  integrated_node_count: number;
  compression_ratio: number;
  target_compression_ratio: number;
  original_edge_count: number;
  integrated_edge_count: number;
}

export interface IntegrationResponse {
  id: string;
  raw_file_ids: string[];
  alignment_id: string | null;
  decisions: IntegrationDecision[];
  integrated_concepts: unknown[];
  compression_stats: CompressionStats;
  generated_at: string;
  metadata: Record<string, unknown>;
}

// ── Dialogue ──

export type DialogueMessageRole = "user" | "assistant";

export interface DialogueMessage {
  id: string;
  role: DialogueMessageRole;
  content: string;
  raw_file_ids: string[];
  teacher_edit_ids: string[];
  created_by: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface DialogueMessageRequest {
  message: string;
  raw_file_ids?: string[];
  created_by?: string | null;
  target_decision_id?: string | null;
}

export interface DialogueMessageResponse {
  user_message: DialogueMessage;
  assistant_message: DialogueMessage;
  edits: unknown[];
  integration: IntegrationResponse | null;
  metadata: Record<string, unknown>;
}

export interface DialogueHistoryResponse {
  raw_file_ids: string[];
  messages: DialogueMessage[];
  count: number;
}
