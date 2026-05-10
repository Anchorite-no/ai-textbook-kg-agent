export type SourceType = "uploaded" | "converted_textbook" | "generated";

export interface SourceLocator {
  raw_file_id: string;
  source_path: string;
  source_type: string;
  locator_text: string;
  page_start: number | null;
  page_end: number | null;
  line_start: number | null;
  line_end: number | null;
  sheet_name: string | null;
  row_start: number | null;
  row_end: number | null;
  slide_number: number | null;
  char_start: number | null;
  char_end: number | null;
  element_ids: string[];
  quote_hash: string | null;
}

export interface RawFile {
  id: string;
  original_filename: string;
  title: string;
  format: string;
  source_type: SourceType;
  storage_path: string;
  sha256: string;
  size_bytes: number;
  page_count: number | null;
  text_char_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
}

export type DocumentElementType =
  | "heading"
  | "paragraph"
  | "table"
  | "figure"
  | "list"
  | "page"
  | "slide"
  | "sheet"
  | "note";

export interface DocumentElement {
  id: string;
  raw_file_id: string;
  type: DocumentElementType;
  text: string;
  order_index: number;
  parent_section_id: string | null;
  source_locator: SourceLocator;
  char_count: number;
  metadata: Record<string, unknown>;
}

export type SectionType = "chapter" | "section" | "page_window" | "slide" | "sheet" | "table";

export interface Section {
  id: string;
  raw_file_id: string;
  title: string;
  section_type: SectionType;
  level: number;
  order_index: number;
  parent_section_id: string | null;
  element_ids: string[];
  content: string;
  char_count: number;
  source_locator: SourceLocator;
  metadata: Record<string, unknown>;
}

export interface Chunk {
  id: string;
  raw_file_id: string;
  section_id: string;
  text: string;
  order_index: number;
  char_start: number;
  char_end: number;
  char_count: number;
  source_locator: SourceLocator;
  metadata: Record<string, unknown>;
}

export type KnowledgeNodeType =
  | "Concept"
  | "Term"
  | "Mechanism"
  | "Process"
  | "Structure"
  | "Function"
  | "Disease"
  | "Symptom"
  | "Pathogen"
  | "Diagnosis"
  | "Treatment"
  | "Experiment"
  | "Example";

export interface KnowledgeNode {
  id: string;
  name: string;
  node_type: KnowledgeNodeType;
  definition: string | null;
  aliases: string[];
  source_locator: SourceLocator;
  evidence_chunk_ids: string[];
  confidence: number;
  metadata: Record<string, unknown>;
}

export type KnowledgeRelationType =
  | "ALIAS_OF"
  | "SAME_AS"
  | "IS_A"
  | "PART_OF"
  | "PREREQUISITE_OF"
  | "CAUSES"
  | "LEADS_TO"
  | "APPLIES_TO"
  | "CONTRASTS_WITH"
  | "EXPLAINS"
  | "EVIDENCED_BY"
  | "MENTIONED_IN"
  | "REFINES"
  | "CONFLICTS_WITH";

export interface KnowledgeEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  relation_type: KnowledgeRelationType;
  description: string | null;
  source_locator: SourceLocator;
  evidence_chunk_ids: string[];
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface ConceptCluster {
  id: string;
  canonical_name: string;
  aliases: string[];
  member_node_ids: string[];
  evidence_chunk_ids: string[];
  confidence: number;
  metadata: Record<string, unknown>;
}

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

export type TeacherEditOperation =
  | "create_node"
  | "update_node"
  | "delete_node"
  | "split_node"
  | "merge_nodes"
  | "create_edge"
  | "update_edge"
  | "override_decision";

export interface TeacherEdit {
  id: string;
  target_type: "node" | "edge" | "decision" | "cluster" | "section" | "chunk";
  target_id: string;
  operation: TeacherEditOperation;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  reason: string | null;
  created_by: string | null;
  created_at: string;
  affected_ids: string[];
  metadata: Record<string, unknown>;
}

export interface RetrievalEvidence {
  id: string;
  query: string;
  chunk_id: string;
  raw_file_id: string;
  source_locator: SourceLocator;
  relevance_score: number;
  answer_span: string | null;
  metadata: Record<string, unknown>;
}

export interface ParsedTextbook {
  id: string;
  raw_file: RawFile;
  elements: DocumentElement[];
  sections: Section[];
  chunks: Chunk[];
  generated_at: string;
  metadata: Record<string, unknown>;
}

export type JobStatus = "queued" | "running" | "completed" | "failed";
export type JobType = "textbook_upload" | "converted_textbook_import";

export interface JobRecord {
  id: string;
  job_type: JobType;
  status: JobStatus;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface TextbookUploadResponse {
  job: JobRecord;
  raw_file_id: string;
  parsed_output_path: string;
  parsed_textbook: ParsedTextbook;
}

export interface TextbookSummary {
  raw_file_id: string;
  title: string;
  format: string;
  page_count: number | null;
  element_count: number;
  section_count: number;
  chunk_count: number;
  parsed_output_path: string;
  updated_at: string;
}

export interface TextbookListResponse {
  textbooks: TextbookSummary[];
}

export interface HealthResponse {
  status: "ok";
  app: string;
  version: string;
  checked_at: string;
}
