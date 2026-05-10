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
    contains = "CONTAINS"
    parallel_with = "PARALLEL_WITH"
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


class GraphResponse(ContractModel):
    id: str
    raw_file_id: str
    title: str
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphBuildRequest(ContractModel):
    raw_file_id: str
    section_ids: list[str] = Field(default_factory=list)
    force_rebuild: bool = False
    max_sections: int = Field(default=200, ge=1, le=3000)
    max_nodes_per_section: int = Field(default=12, ge=1, le=80)
    use_llm: bool = True


class GraphNodeDetailResponse(ContractModel):
    node: KnowledgeNode
    edges: list[KnowledgeEdge] = Field(default_factory=list)
    related_nodes: list[KnowledgeNode] = Field(default_factory=list)
    evidence_chunks: list[Chunk] = Field(default_factory=list)
    graph_id: str
    raw_file_id: str


class LayeredGraphLayerType(str, Enum):
    document_tree = "document_tree"
    concept_kg = "concept_kg"
    alias_alignment = "alias_alignment"
    evidence_graph = "evidence_graph"
    integration_decision = "integration_decision"
    teacher_edit = "teacher_edit"
    graphrag_retrieval = "graphrag_retrieval"


class LayeredGraphLayerStatus(str, Enum):
    ready = "ready"
    empty = "empty"
    reserved = "reserved"


class LayeredGraphLayer(ContractModel):
    layer_type: LayeredGraphLayerType
    display_name: str
    status: LayeredGraphLayerStatus
    node_count: int = 0
    edge_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayeredGraphNode(ContractModel):
    id: str
    layer_type: LayeredGraphLayerType
    label: str
    node_type: str
    ref_id: str | None = None
    source_locator: SourceLocator
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayeredGraphEdge(ContractModel):
    id: str
    layer_type: LayeredGraphLayerType
    source_node_id: str
    target_node_id: str
    relation_type: str
    ref_id: str | None = None
    source_locator: SourceLocator
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayeredGraphResponse(ContractModel):
    id: str
    raw_file_id: str
    title: str
    layers: list[LayeredGraphLayer]
    nodes: list[LayeredGraphNode]
    edges: list[LayeredGraphEdge]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayeredGraphBuildRequest(ContractModel):
    raw_file_id: str
    force_rebuild: bool = False
    build_missing_concept_graph: bool = True
    max_sections: int = Field(default=200, ge=1, le=3000)
    max_nodes_per_section: int = Field(default=12, ge=1, le=80)
    use_llm: bool = True


class ConceptCluster(ContractModel):
    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    member_node_ids: list[str]
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlignmentRelationType(str, Enum):
    same_as = "SAME_AS"
    alias_of = "ALIAS_OF"
    refines = "REFINES"
    conflicts_with = "CONFLICTS_WITH"


class AlignmentSignal(ContractModel):
    name: str
    score: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    detail: str | None = None


class AlignmentCandidate(ContractModel):
    id: str
    source_node_id: str
    target_node_id: str
    relation_type: AlignmentRelationType
    confidence: float = Field(ge=0, le=1)
    signals: list[AlignmentSignal] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    source_locators: list[SourceLocator] = Field(default_factory=list)
    reason: str
    needs_teacher_review: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AliasRecord(ContractModel):
    id: str
    alias: str
    canonical_name: str
    node_ids: list[str] = Field(default_factory=list)
    relation_type: AlignmentRelationType = AlignmentRelationType.alias_of
    confidence: float = Field(ge=0, le=1)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    source_locators: list[SourceLocator] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalConcept(ContractModel):
    id: str
    canonical_name: str
    cluster_id: str
    aliases: list[str] = Field(default_factory=list)
    member_node_ids: list[str] = Field(default_factory=list)
    definition: str | None = None
    source_locators: list[SourceLocator] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlignmentBuildRequest(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    force_rebuild: bool = False
    min_confidence: float = Field(default=0.62, ge=0, le=1)
    include_singletons: bool = False
    max_nodes: int = Field(default=1000, ge=2, le=10000)


class AlignmentResponse(ContractModel):
    id: str
    raw_file_ids: list[str] = Field(default_factory=list)
    canonical_concepts: list[CanonicalConcept] = Field(default_factory=list)
    aliases: list[AliasRecord] = Field(default_factory=list)
    clusters: list[ConceptCluster] = Field(default_factory=list)
    candidates: list[AlignmentCandidate] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
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
    source_locators: list[SourceLocator] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompressionStats(ContractModel):
    original_char_count: int = Field(ge=0)
    retained_char_count: int = Field(ge=0)
    original_node_count: int = Field(ge=0)
    integrated_node_count: int = Field(ge=0)
    merged_node_count: int = Field(ge=0)
    kept_node_count: int = Field(ge=0)
    removed_node_count: int = Field(ge=0)
    refined_node_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    target_compression_ratio: float = Field(ge=0, le=1)
    compression_ratio: float = Field(ge=0)
    node_reduction_ratio: float = Field(ge=0, le=1, default=0.0)
    evidence_coverage_ratio: float = Field(ge=0, le=1, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegratedConcept(ContractModel):
    id: str
    canonical_name: str
    member_node_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    definition: str
    summary: str | None = None
    source_locators: list[SourceLocator] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationBuildRequest(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    force_rebuild: bool = False
    target_compression_ratio: float = Field(default=0.30, gt=0, le=0.80)
    alignment_min_confidence: float = Field(default=0.62, ge=0, le=1)
    include_keep_decisions: bool = True
    max_nodes: int = Field(default=1000, ge=2, le=10000)


class IntegrationResponse(ContractModel):
    id: str
    raw_file_ids: list[str] = Field(default_factory=list)
    alignment_id: str | None = None
    decisions: list[IntegrationDecision] = Field(default_factory=list)
    integrated_concepts: list[IntegratedConcept] = Field(default_factory=list)
    compression_stats: CompressionStats
    generated_at: datetime = Field(default_factory=datetime.utcnow)
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


class TeacherEditCreateRequest(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    target_type: Literal["node", "edge", "decision", "cluster", "section", "chunk"]
    target_id: str
    operation: TeacherEditOperation
    after: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionOverrideRequest(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    action: IntegrationAction
    retained_content: str | None = None
    removed_redundancy: str | None = None
    reason: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    created_by: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TeacherEditApplyResponse(ContractModel):
    edit: TeacherEdit
    integration: IntegrationResponse | None = None
    decision: IntegrationDecision | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TeacherEditListResponse(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    edits: list[TeacherEdit] = Field(default_factory=list)
    count: int = 0


class DialogueMessageRole(str, Enum):
    teacher = "teacher"
    assistant = "assistant"
    system = "system"


class DialogueMessage(ContractModel):
    id: str
    role: DialogueMessageRole
    content: str
    raw_file_ids: list[str] = Field(default_factory=list)
    teacher_edit_ids: list[str] = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DialogueMessageRequest(ContractModel):
    message: str
    raw_file_ids: list[str] = Field(default_factory=list)
    created_by: str | None = None
    target_decision_id: str | None = None
    override_action: IntegrationAction | None = None
    retained_content: str | None = None
    removed_redundancy: str | None = None
    reason: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DialogueMessageResponse(ContractModel):
    user_message: DialogueMessage
    assistant_message: DialogueMessage
    edits: list[TeacherEdit] = Field(default_factory=list)
    integration: IntegrationResponse | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DialogueHistoryResponse(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    messages: list[DialogueMessage] = Field(default_factory=list)
    count: int = 0


class RetrievalEvidence(ContractModel):
    id: str
    query: str
    chunk_id: str
    raw_file_id: str
    source_locator: SourceLocator
    relevance_score: float = Field(ge=0, le=1)
    answer_span: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIndexRequest(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    force_rebuild: bool = False
    max_chunks: int | None = Field(default=None, ge=1, le=200000)


class RagIndexStatus(ContractModel):
    status: Literal["empty", "ready"]
    textbook_count: int = 0
    chunk_count: int = 0
    raw_file_ids: list[str] = Field(default_factory=list)
    index_path: str | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagQueryRequest(ContractModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    raw_file_ids: list[str] = Field(default_factory=list)


class RagCitation(ContractModel):
    chunk_id: str
    raw_file_id: str
    textbook: str
    chapter: str | None = None
    source_locator: SourceLocator
    relevance_score: float = Field(ge=0, le=1)
    quote: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagQueryResponse(ContractModel):
    question: str
    answer: str
    citations: list[RagCitation] = Field(default_factory=list)
    source_chunks: list[Chunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRagIntent(str, Enum):
    definition = "definition"
    coverage = "coverage"
    comparison = "comparison"
    prerequisite = "prerequisite"
    relation_path = "relation_path"
    decision_review = "decision_review"
    hybrid = "hybrid"


class GraphRagQueryRequest(ContractModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    raw_file_ids: list[str] = Field(default_factory=list)
    max_path_depth: int = Field(default=2, ge=1, le=4)
    include_decisions: bool = True


class GraphRagNodeHit(ContractModel):
    node: KnowledgeNode
    raw_file_id: str
    textbook: str
    score: float = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)
    matched_aliases: list[str] = Field(default_factory=list)
    source_locator: SourceLocator
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRagPathStep(ContractModel):
    source_node_id: str
    source_node_name: str
    target_node_id: str
    target_node_name: str
    relation_type: KnowledgeRelationType
    description: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.0)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    source_locator: SourceLocator
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRagPath(ContractModel):
    id: str
    path_type: str
    node_ids: list[str] = Field(default_factory=list)
    node_names: list[str] = Field(default_factory=list)
    steps: list[GraphRagPathStep] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRagQueryResponse(ContractModel):
    question: str
    intent: GraphRagIntent
    answer: str
    citations: list[RagCitation] = Field(default_factory=list)
    source_chunks: list[Chunk] = Field(default_factory=list)
    node_hits: list[GraphRagNodeHit] = Field(default_factory=list)
    paths: list[GraphRagPath] = Field(default_factory=list)
    decisions: list[IntegrationDecision] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRagStatus(ContractModel):
    status: Literal["empty", "partial", "ready"]
    rag_index_status: RagIndexStatus
    graph_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    alignment_available: bool = False
    integration_available: bool = False
    raw_file_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportGenerateRequest(ContractModel):
    raw_file_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    include_integration: bool = True
    include_graph_metrics: bool = True
    include_dataset_metrics: bool = True
    use_llm: bool = True


class ReportGenerateResponse(ContractModel):
    id: str
    raw_file_ids: list[str] = Field(default_factory=list)
    title: str
    markdown: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
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
    textbook_pipeline = "textbook_pipeline"
    large_file_upload = "large_file_upload"
    graph_build = "graph_build"
    layered_kg_build = "layered_kg_build"
    alignment_build = "alignment_build"
    integration_build = "integration_build"
    rag_index = "rag_index"
    converted_textbook_import = "converted_textbook_import"
    dataset_prepare = "dataset_prepare"
    organize_workflow = "organize_workflow"


class PipelineStepStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class PipelineStepName(str, Enum):
    assemble_file = "assemble_file"
    detect_format = "detect_format"
    parse_elements = "parse_elements"
    build_sections = "build_sections"
    chunk_sections = "chunk_sections"
    persist_parsed = "persist_parsed"


class PipelineStepRecord(ContractModel):
    name: PipelineStepName
    status: PipelineStepStatus = PipelineStepStatus.queued
    progress: int = Field(ge=0, le=100, default=0)
    message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


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
    steps: list[PipelineStepRecord] = Field(default_factory=list)
    retryable: bool = False
    context_path: str | None = None


class GraphBuildResponse(ContractModel):
    job: JobRecord
    raw_file_id: str
    graph_output_path: str
    graph: GraphResponse


class LayeredGraphBuildResponse(ContractModel):
    job: JobRecord
    raw_file_id: str
    layered_graph_output_path: str
    layered_graph: LayeredGraphResponse


class AlignmentBuildResponse(ContractModel):
    job: JobRecord
    alignment_output_path: str
    alignment: AlignmentResponse


class IntegrationBuildResponse(ContractModel):
    job: JobRecord
    integration_output_path: str
    integration: IntegrationResponse


class RagIndexResponse(ContractModel):
    job: JobRecord
    status: RagIndexStatus


class TextbookUploadResponse(ContractModel):
    job: JobRecord
    raw_file_id: str
    parsed_output_path: str
    parsed_textbook: ParsedTextbook


class AsyncTextbookParseResponse(ContractModel):
    job: JobRecord
    accepted: bool = True
    upload_session_id: str | None = None


class JobRetryResponse(ContractModel):
    job: JobRecord
    accepted: bool = True


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


class UploadSessionStatus(str, Enum):
    created = "created"
    uploading = "uploading"
    assembling = "assembling"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"


class UploadSessionCreateRequest(ContractModel):
    filename: str
    total_size_bytes: int = Field(ge=1)
    total_chunks: int = Field(ge=1)
    chunk_size_bytes: int = Field(ge=1)
    sha256: str | None = None
    content_type: str | None = None
    parse_on_complete: bool = True


class UploadSessionRecord(ContractModel):
    id: str
    filename: str
    total_size_bytes: int
    total_chunks: int
    chunk_size_bytes: int
    sha256: str | None = None
    content_type: str | None = None
    parse_on_complete: bool = True
    status: UploadSessionStatus = UploadSessionStatus.created
    uploaded_chunks: list[int] = Field(default_factory=list)
    missing_chunks: list[int] = Field(default_factory=list)
    received_bytes: int = 0
    upload_progress: int = Field(ge=0, le=100, default=0)
    parse_progress: int = Field(ge=0, le=100, default=0)
    job_id: str | None = None
    assembled_path: str | None = None
    raw_file_id: str | None = None
    parsed_output_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UploadChunkResponse(ContractModel):
    session: UploadSessionRecord
    chunk_index: int
    received_bytes: int


class UploadSessionCompleteResponse(ContractModel):
    session: UploadSessionRecord
    job: JobRecord
    parsed_upload: TextbookUploadResponse | None = None


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


class SampleBookSummary(ContractModel):
    title: str
    raw_file_id: str
    source_sha256_16: str | None = None
    page_count: int | None = None
    text_char_count: int | None = None
    parsed_ready: bool = False
    graph_ready: bool = False
    layered_graph_ready: bool = False
    chunk_count: int = 0
    section_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    endpoints: dict[str, str] = Field(default_factory=dict)


class SampleDatasetResponse(ContractModel):
    id: str
    title: str
    status: Literal["missing_materials", "not_prepared", "partial", "ready"]
    book_count: int = 0
    books: list[SampleBookSummary] = Field(default_factory=list)
    raw_file_ids: list[str] = Field(default_factory=list)
    rag_ready: bool = False
    alignment_ready: bool = False
    integration_ready: bool = False
    graphrag_ready: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)
    endpoints: dict[str, str] = Field(default_factory=dict)
    message: str | None = None


class SampleDatasetPrepareRequest(ContractModel):
    force_rebuild: bool = False
    build_graph: bool = True
    build_layered_graph: bool = False
    build_rag: bool = True
    build_alignment: bool = True
    build_integration: bool = True
    use_llm: bool = False
    max_sections: int = Field(default=1000, ge=1, le=3000)
    max_nodes_per_section: int = Field(default=12, ge=1, le=80)
    alignment_min_confidence: float = Field(default=0.62, ge=0, le=1)
    alignment_max_nodes: int = Field(default=4000, ge=2, le=10000)
    integration_target_compression_ratio: float = Field(default=0.30, gt=0, le=0.80)
    integration_max_nodes: int = Field(default=4000, ge=2, le=10000)


class SampleDatasetPrepareResponse(ContractModel):
    job: JobRecord
    accepted: bool = True
    dataset: SampleDatasetResponse


class OrganizeWorkflowAcceptedResponse(ContractModel):
    job: JobRecord
    accepted: bool = True
    raw_file_ids: list[str] = Field(default_factory=list)
    message: str
