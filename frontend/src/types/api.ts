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
export type AsyncTextbookParseResponse = Schemas["AsyncTextbookParseResponse"];
export type SampleBookSummary = Schemas["SampleBookSummary"];
export type SampleDatasetResponse = Schemas["SampleDatasetResponse"];
export type SampleDatasetPrepareRequest = Schemas["SampleDatasetPrepareRequest"];
export type SampleDatasetPrepareResponse = Schemas["SampleDatasetPrepareResponse"];
export type OrganizeWorkflowAcceptedResponse = Schemas["OrganizeWorkflowAcceptedResponse"];
export type JobRetryResponse = Schemas["JobRetryResponse"];

export type KnowledgeNode = Schemas["KnowledgeNode"];
export type KnowledgeNodeType = Schemas["KnowledgeNodeType"];
export type KnowledgeEdge = Schemas["KnowledgeEdge"];
export type KnowledgeRelationType = Schemas["KnowledgeRelationType"];
export type GraphResponse = Schemas["GraphResponse"];
export type GraphBuildRequest = Schemas["GraphBuildRequest"];
export type GraphBuildResponse = Schemas["GraphBuildResponse"];
export type GraphNodeDetailResponse = Schemas["GraphNodeDetailResponse"];
export type LayeredGraphBuildRequest = Schemas["LayeredGraphBuildRequest"];
export type LayeredGraphBuildResponse = Schemas["LayeredGraphBuildResponse"];
export type LayeredGraphResponse = Schemas["LayeredGraphResponse"];

export type RagIndexRequest = Schemas["RagIndexRequest"];
export type RagIndexStatus = Schemas["RagIndexStatus"];
export type RagIndexResponse = Schemas["RagIndexResponse"];
export type RagQueryRequest = Schemas["RagQueryRequest"];
export type RagCitation = Schemas["RagCitation"];
export type RagQueryResponse = Schemas["RagQueryResponse"];
export type GraphRagQueryRequest = Schemas["GraphRagQueryRequest"];
export type GraphRagQueryResponse = Schemas["GraphRagQueryResponse"];
export type GraphRagStatus = Schemas["GraphRagStatus"];
export type GraphRagNodeHit = Schemas["GraphRagNodeHit"];
export type GraphRagPath = Schemas["GraphRagPath"];
export type ReportGenerateRequest = Schemas["ReportGenerateRequest"];
export type ReportGenerateResponse = Schemas["ReportGenerateResponse"];

export type AlignmentBuildRequest = Schemas["AlignmentBuildRequest"];
export type AlignmentResponse = Schemas["AlignmentResponse"];
export type AlignmentBuildResponse = Schemas["AlignmentBuildResponse"];
export type IntegrationAction = Schemas["IntegrationAction"];
export type IntegrationBuildRequest = Schemas["IntegrationBuildRequest"];
export type IntegrationDecision = Schemas["IntegrationDecision"];
export type IntegratedConcept = Schemas["IntegratedConcept"];
export type CompressionStats = Schemas["CompressionStats"];
export type IntegrationResponse = Schemas["IntegrationResponse"];
export type IntegrationBuildResponse = Schemas["IntegrationBuildResponse"];

export type DialogueMessageRole = Schemas["DialogueMessageRole"];
export type DialogueMessage = Schemas["DialogueMessage"];
export type DialogueMessageRequest = Schemas["DialogueMessageRequest"];
export type DialogueMessageResponse = Schemas["DialogueMessageResponse"];
export type DialogueHistoryResponse = Schemas["DialogueHistoryResponse"];
export type TeacherEdit = Schemas["TeacherEdit"];
export type TeacherEditCreateRequest = Schemas["TeacherEditCreateRequest"];
export type TeacherEditApplyResponse = Schemas["TeacherEditApplyResponse"];
export type TeacherEditListResponse = Schemas["TeacherEditListResponse"];
export type DecisionOverrideRequest = Schemas["DecisionOverrideRequest"];

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
