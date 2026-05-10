import type { AsyncTextbookParseResponse, TextbookSummary, TextbookUploadResponse, ParsedTextbook } from "@/types/api";

const fixture: TextbookSummary[] = [
  {
    raw_file_id: "raw_mock_a",
    title: "生理学（示例 A）",
    format: "pdf",
    page_count: 482,
    element_count: 482,
    section_count: 96,
    chunk_count: 1240,
    parsed_output_path: "data/parsed/raw_mock_a.json",
    updated_at: new Date().toISOString()
  },
  {
    raw_file_id: "raw_mock_b",
    title: "病理生理学（示例 B）",
    format: "pdf",
    page_count: 358,
    element_count: 358,
    section_count: 72,
    chunk_count: 920,
    parsed_output_path: "data/parsed/raw_mock_b.json",
    updated_at: new Date().toISOString()
  }
];

export async function listTextbooks(): Promise<TextbookSummary[]> {
  await new Promise((r) => setTimeout(r, 220));
  return fixture;
}

export async function uploadTextbook(file: File): Promise<TextbookUploadResponse> {
  await new Promise((r) => setTimeout(r, 800));
  const summary: TextbookSummary = {
    raw_file_id: `raw_mock_${Date.now()}`,
    title: file.name.replace(/\.[^.]+$/, ""),
    format: file.name.split(".").pop() ?? "pdf",
    page_count: null,
    element_count: 0,
    section_count: 0,
    chunk_count: 0,
    parsed_output_path: "",
    updated_at: new Date().toISOString()
  };
  return {
    job: {
      id: `job_mock_${Date.now()}`,
      job_type: "textbook_upload",
      status: "completed",
      progress: 100,
      message: "",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      result: null,
      error: null,
      context_path: null,
      retryable: false
    },
    raw_file_id: summary.raw_file_id,
    parsed_output_path: summary.parsed_output_path,
    parsed_textbook: {
      id: `parsed_${summary.raw_file_id}`,
      raw_file: {
        id: summary.raw_file_id,
        original_filename: file.name,
        title: summary.title,
        format: summary.format,
        source_type: "uploaded",
        storage_path: `uploads/${summary.raw_file_id}`,
        sha256: "",
        size_bytes: file.size,
        page_count: null,
        text_char_count: 0,
        created_at: new Date().toISOString(),
        metadata: {}
      },
      elements: [],
      sections: [],
      chunks: []
    }
  };
}

export async function uploadTextbookAsync(_file: File): Promise<AsyncTextbookParseResponse> {
  await new Promise((r) => setTimeout(r, 300));
  return { job: mockJob("textbook_pipeline"), accepted: true, upload_session_id: null };
}

export async function parseTextbook(rawFileId: string): Promise<TextbookUploadResponse> {
  await new Promise((r) => setTimeout(r, 1200));
  const parsed = mockParsed(rawFileId);
  return { job: mockJob("textbook_parse"), raw_file_id: rawFileId, parsed_output_path: `data/parsed/${rawFileId}.json`, parsed_textbook: parsed };
}

export async function parseTextbookAsync(_rawFileId: string): Promise<AsyncTextbookParseResponse> {
  await new Promise((r) => setTimeout(r, 300));
  return { job: mockJob("textbook_pipeline"), accepted: true, upload_session_id: null };
}

export async function getTextbook(rawFileId: string): Promise<ParsedTextbook> {
  await new Promise((r) => setTimeout(r, 400));
  return mockParsed(rawFileId);
}

function mockJob(jobType: "textbook_pipeline" | "textbook_parse") {
  return {
    id: `job_mock_${Date.now()}`,
    job_type: jobType,
    status: "completed" as const,
    progress: 100,
    message: "mock",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result: null,
    error: null,
    context_path: null,
    retryable: false,
    steps: []
  };
}

function mockParsed(rawFileId: string): ParsedTextbook {
  const title = fixture.find((item) => item.raw_file_id === rawFileId)?.title ?? rawFileId;
  const locator = {
    raw_file_id: rawFileId,
    source_path: `mock/${rawFileId}.pdf`,
    source_type: "converted_textbook",
    locator_text: `${title} page 1`,
    page_start: 1,
    page_end: 1,
    line_start: null,
    line_end: null,
    sheet_name: null,
    row_start: null,
    row_end: null,
    slide_number: null,
    char_start: null,
    char_end: null,
    element_ids: ["elem_mock_1"],
    quote_hash: "mock"
  };
  return {
    id: `parsed_${rawFileId}`,
    raw_file: {
      id: rawFileId,
      original_filename: `${title}.pdf`,
      title,
      format: "pdf",
      source_type: "converted_textbook",
      storage_path: `mock/${rawFileId}.pdf`,
      sha256: rawFileId.replace("raw_", ""),
      size_bytes: 0,
      page_count: 1,
      text_char_count: 80,
      created_at: new Date().toISOString(),
      metadata: {}
    },
    elements: [],
    sections: [
      {
        id: `sec_${rawFileId}_1`,
        raw_file_id: rawFileId,
        title: "第一章 示例章节",
        section_type: "chapter",
        level: 1,
        order_index: 0,
        parent_section_id: null,
        element_ids: ["elem_mock_1"],
        content: "示例章节内容",
        char_count: 80,
        source_locator: locator,
        metadata: {}
      }
    ],
    chunks: []
  };
}
