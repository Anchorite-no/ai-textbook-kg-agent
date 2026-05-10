import type {
  GraphRagQueryResponse,
  GraphRagStatus,
  RagIndexRequest,
  RagIndexResponse,
  RagIndexStatus,
  RagQueryResponse
} from "@/types/api";

export async function indexRAG(_body: RagIndexRequest): Promise<RagIndexResponse> {
  await new Promise((r) => setTimeout(r, 300));
  const status: RagIndexStatus = {
    status: "ready",
    textbook_count: 2,
    chunk_count: 2160,
    raw_file_ids: ["raw_mock_a", "raw_mock_b"],
    index_path: null,
    updated_at: new Date().toISOString(),
    metadata: {}
  };
  return {
    job: {
      id: `job_rag_index_${Date.now()}`,
      job_type: "rag_index",
      status: "completed",
      progress: 100,
      message: "RAG 证据索引已建立",
      result: null,
      error: null,
      retryable: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    },
    status
  };
}

export async function getRAGStatus(): Promise<RagIndexStatus> {
  await new Promise((r) => setTimeout(r, 200));
  return {
    status: "ready",
    textbook_count: 2,
    chunk_count: 2160,
    raw_file_ids: ["raw_mock_a", "raw_mock_b"],
    index_path: null,
    updated_at: new Date().toISOString(),
    metadata: {}
  };
}

export async function queryRAG(question: string, _topK = 5): Promise<RagQueryResponse> {
  await new Promise((r) => setTimeout(r, 600));
  return {
    question,
    answer: `这是对「${question}」的 mock 回答。实际回答需要后端 RAG 服务生成。`,
    citations: [
      {
        chunk_id: "chunk_mock_1",
        raw_file_id: "raw_mock_a",
        textbook: "生理学（第九版）",
        chapter: "第二章 循环系统",
        source_locator: {
          raw_file_id: "raw_mock_a",
          source_path: "materials/raw_mock_a.pdf",
          source_type: "converted_textbook",
          locator_text: "raw_mock_a page 12",
          page_start: 12, page_end: 12,
          line_start: null, line_end: null,
          sheet_name: null, row_start: null, row_end: null,
          slide_number: null, char_start: null, char_end: null,
          element_ids: [], quote_hash: null
        },
        relevance_score: 0.92,
        quote: "心脏是推动血液循环的中空肌性器官，分为四个腔室。",
        metadata: {}
      }
    ],
    source_chunks: [],
    metadata: {}
  };
}

export async function getGraphRAGStatus(): Promise<GraphRagStatus> {
  return {
    status: "ready",
    rag_index_status: await getRAGStatus(),
    graph_count: 2,
    node_count: 50,
    edge_count: 90,
    alignment_available: true,
    integration_available: true,
    raw_file_ids: ["raw_mock_a", "raw_mock_b"],
    metadata: {}
  };
}

export async function queryGraphRAG(question: string): Promise<GraphRagQueryResponse> {
  const res = await queryRAG(question);
  return {
    question,
    intent: "hybrid",
    answer: res.answer,
    citations: res.citations,
    source_chunks: res.source_chunks,
    node_hits: [],
    paths: [],
    decisions: [],
    metadata: { mock: true }
  };
}
