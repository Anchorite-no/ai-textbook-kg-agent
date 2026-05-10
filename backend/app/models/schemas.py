from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SourceLocator(ContractModel):
    raw_file_id: str
    source_path: str
    source_type: str
    locator_text: str
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    slide_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    element_ids: list[str] = Field(default_factory=list)
    quote_hash: str | None = None


class RawFile(ContractModel):
    id: str
    original_filename: str
    title: str
    format: str
    source_type: Literal["uploaded", "converted_textbook", "generated"] = "uploaded"
    storage_path: str
    sha256: str
    size_bytes: int
    page_count: int | None = None
    text_char_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentElementType(str, Enum):
    heading = "heading"
    paragraph = "paragraph"
    table = "table"
    figure = "figure"
    list = "list"
    page = "page"
    slide = "slide"
    sheet = "sheet"
    note = "note"


class DocumentElement(ContractModel):
    id: str
    raw_file_id: str
    type: DocumentElementType
    text: str
    order_index: int
    parent_section_id: str | None = None
    source_locator: SourceLocator
    char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionType(str, Enum):
    chapter = "chapter"
    section = "section"
    page_window = "page_window"
    slide = "slide"
    sheet = "sheet"
    table = "table"


class Section(ContractModel):
    id: str
    raw_file_id: str
    title: str
    section_type: SectionType = SectionType.section
    level: int = 1
    order_index: int
    parent_section_id: str | None = None
    element_ids: list[str]
    content: str
    char_count: int
    source_locator: SourceLocator
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(ContractModel):
    id: str
    raw_file_id: str
    section_id: str
    text: str
    order_index: int
    char_start: int
    char_end: int
    char_count: int
    source_locator: SourceLocator
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeNodeType(str, Enum):
    concept = "Concept"
    term = "Term"
    mechanism = "Mechanism"
    process = "Process"
    structure = "Structure"
    function = "Function"
    disease = "Disease"
    symptom = "Symptom"
    pathogen = "Pathogen"
    diagnosis = "Diagnosis"
    treatment = "Treatment"
    experiment = "Experiment"
    example = "Example"


class KnowledgeNode(ContractModel):
    id: str
    name: str
    node_type: KnowledgeNodeType
    definition: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_locator: SourceLocator
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeRelationType(str, Enum):
    alias_of = "ALIAS_OF"
    same_as = "SAME_AS"
    is_a = "IS_A"
    part_of = "PART_OF"
    prerequisite_of = "PREREQUISITE_OF"
    causes = "CAUSES"
    leads_to = "LEADS_TO"
    applies_to = "APPLIES_TO"
    contrasts_with = "CONTRASTS_WITH"
    explains = "EXPLAINS"
    evidenced_by = "EVIDENCED_BY"
    mentioned_in = "MENTIONED_IN"
    refines = "REFINES"
    conflicts_with = "CONFLICTS_WITH"


class KnowledgeEdge(ContractModel):
    id: str
    source_node_id: str
    target_node_id: str
    relation_type: KnowledgeRelationType
    description: str | None = None
    source_locator: SourceLocator
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConceptCluster(ContractModel):
    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    member_node_ids: list[str]
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationAction(str, Enum):
    merge = "merge"
    keep = "keep"
    remove = "remove"
    refine = "refine"
    conflict = "conflict"


class IntegrationDecision(ContractModel):
    id: str
    cluster_id: str | None = None
    action: IntegrationAction
    target_node_ids: list[str] = Field(default_factory=list)
    retained_content: str | None = None
    removed_redundancy: str | None = None
    reason: str
    confidence: float = Field(ge=0, le=1, default=0.0)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TeacherEditOperation(str, Enum):
    create_node = "create_node"
    update_node = "update_node"
    delete_node = "delete_node"
    split_node = "split_node"
    merge_nodes = "merge_nodes"
    create_edge = "create_edge"
    update_edge = "update_edge"
    override_decision = "override_decision"


class TeacherEdit(ContractModel):
    id: str
    target_type: Literal["node", "edge", "decision", "cluster", "section", "chunk"]
    target_id: str
    operation: TeacherEditOperation
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    affected_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalEvidence(ContractModel):
    id: str
    query: str
    chunk_id: str
    raw_file_id: str
    source_locator: SourceLocator
    relevance_score: float = Field(ge=0, le=1)
    answer_span: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedTextbook(ContractModel):
    id: str
    raw_file: RawFile
    elements: list[DocumentElement]
    sections: list[Section]
    chunks: list[Chunk]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(ContractModel):
    status: Literal["ok"]
    app: str
    version: str
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class ApiErrorResponse(ContractModel):
    message: str
    code: str
    detail: str | None = None


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobType(str, Enum):
    textbook_upload = "textbook_upload"
    textbook_batch_upload = "textbook_batch_upload"
    textbook_parse = "textbook_parse"
    converted_textbook_import = "converted_textbook_import"


class JobRecord(ContractModel):
    id: str
    job_type: JobType
    status: JobStatus
    progress: int = Field(ge=0, le=100, default=0)
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: dict[str, Any] | None = None
    error: str | None = None


class TextbookUploadResponse(ContractModel):
    job: JobRecord
    raw_file_id: str
    parsed_output_path: str
    parsed_textbook: ParsedTextbook


class TextbookUploadError(ContractModel):
    filename: str
    error: str
    job: JobRecord | None = None


class TextbookBatchUploadResponse(ContractModel):
    job: JobRecord
    items: list[TextbookUploadResponse]
    errors: list[TextbookUploadError] = Field(default_factory=list)
    total_count: int
    success_count: int
    failed_count: int


class TextbookSummary(ContractModel):
    raw_file_id: str
    title: str
    format: str
    page_count: int | None = None
    element_count: int
    section_count: int
    chunk_count: int
    parsed_output_path: str
    updated_at: datetime


class TextbookListResponse(ContractModel):
    textbooks: list[TextbookSummary]
