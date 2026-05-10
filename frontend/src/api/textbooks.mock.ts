import type { TextbookSummary, TextbookUploadResponse, ParsedTextbook } from "@/types/api";

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

export async function uploadTextbookAsync(file: File): Promise<{ job_id: string }> {
  await new Promise((r) => setTimeout(r, 300));
  return { job_id: `job_mock_${Date.now()}` };
}

export async function parseTextbook(rawFileId: string): Promise<ParsedTextbook> {
  await new Promise((r) => setTimeout(r, 1200));
  throw new Error("Mock parseTextbook not implemented");
}

export async function parseTextbookAsync(rawFileId: string): Promise<{ job_id: string }> {
  await new Promise((r) => setTimeout(r, 300));
  return { job_id: `job_parse_${Date.now()}` };
}

export async function getTextbook(rawFileId: string): Promise<ParsedTextbook> {
  await new Promise((r) => setTimeout(r, 400));
  throw new Error("Mock getTextbook not implemented");
}
