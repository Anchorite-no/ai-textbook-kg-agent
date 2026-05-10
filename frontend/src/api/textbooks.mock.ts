import type { TextbookSummary } from "@/types/api";

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
