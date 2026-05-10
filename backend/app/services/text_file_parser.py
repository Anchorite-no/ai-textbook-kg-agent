from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.models.schemas import (
    Chunk,
    DocumentElement,
    DocumentElementType,
    ParsedTextbook,
    RawFile,
    Section,
    SectionType,
    SourceLocator,
)
from app.services.converted_textbook_importer import quote_hash, stable_id


CHUNK_SIZE = 700
CHUNK_OVERLAP = 80
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


@dataclass(frozen=True)
class LineRecord:
    line_number: int
    text: str


@dataclass(frozen=True)
class LineSpan:
    line_start: int
    line_end: int
    start: int
    end: int
    element_ids: list[str]


@dataclass
class SectionDraft:
    title: str
    level: int
    section_type: SectionType
    lines: list[LineRecord]


def parse_uploaded_text_file(file_path: Path, original_filename: str | None = None) -> tuple[ParsedTextbook, Path]:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_TEXT_EXTENSIONS:
        raise ValueError(f"Unsupported text parser format: {suffix}")

    raw_bytes = file_path.read_bytes()
    text = _decode_text(raw_bytes)
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    filename = original_filename or file_path.name
    title = Path(filename).stem
    raw_file_id = f"raw_{sha256[:16]}"

    raw_file = RawFile(
        id=raw_file_id,
        original_filename=filename,
        title=title,
        format=suffix.lstrip("."),
        source_type="uploaded",
        storage_path=str(file_path),
        sha256=sha256,
        size_bytes=len(raw_bytes),
        page_count=None,
        text_char_count=len(text),
        metadata={"parser": "text_file_parser"},
    )

    line_records = _to_line_records(text)
    elements = _build_line_elements(raw_file, line_records)
    sections = _build_text_sections(raw_file, line_records, elements, suffix)
    chunks = _build_chunks(raw_file, sections)

    parsed = ParsedTextbook(
        id=stable_id("parsed", raw_file.id, sha256),
        raw_file=raw_file,
        elements=elements,
        sections=sections,
        chunks=chunks,
        metadata={
            "source_pipeline": "uploaded_text_file",
            "section_strategy": "markdown_headings" if suffix in {".md", ".markdown"} else "text_headings",
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "element_count": len(elements),
            "section_count": len(sections),
            "chunk_count": len(chunks),
        },
    )
    output_path = settings.parsed_data_dir / f"{raw_file.id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(parsed.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return parsed, output_path


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _to_line_records(text: str) -> list[LineRecord]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [LineRecord(index, line.rstrip()) for index, line in enumerate(normalized.split("\n"), start=1)]


def _build_line_elements(raw_file: RawFile, lines: list[LineRecord]) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    for order_index, line in enumerate(lines):
        if not line.text.strip():
            continue
        element_type = DocumentElementType.heading if _heading_marker(line.text, raw_file.format) else DocumentElementType.paragraph
        locator = SourceLocator(
            raw_file_id=raw_file.id,
            source_path=raw_file.storage_path,
            source_type=raw_file.source_type,
            locator_text=f"{raw_file.title} line {line.line_number}",
            line_start=line.line_number,
            line_end=line.line_number,
            quote_hash=quote_hash(line.text),
        )
        elements.append(
            DocumentElement(
                id=stable_id("elem", raw_file.id, "line", line.line_number),
                raw_file_id=raw_file.id,
                type=element_type,
                text=line.text,
                order_index=order_index,
                source_locator=locator,
                char_count=len(line.text),
                metadata={"line_number": line.line_number},
            )
        )
    return elements


def _build_text_sections(
    raw_file: RawFile,
    lines: list[LineRecord],
    elements: list[DocumentElement],
    suffix: str,
) -> list[Section]:
    drafts = _draft_sections(lines, suffix)
    element_by_line = {int(element.metadata["line_number"]): element for element in elements}
    sections: list[Section] = []

    for order_index, draft in enumerate(drafts):
        content, line_spans = _compose_section_content(draft.lines, element_by_line)
        if not content.strip() or not line_spans:
            continue
        line_start = line_spans[0].line_start
        line_end = line_spans[-1].line_end
        element_ids = list(dict.fromkeys(element_id for span in line_spans for element_id in span.element_ids))
        locator = SourceLocator(
            raw_file_id=raw_file.id,
            source_path=raw_file.storage_path,
            source_type=raw_file.source_type,
            locator_text=f"{raw_file.title} lines {line_start}-{line_end}",
            line_start=line_start,
            line_end=line_end,
            element_ids=element_ids,
            quote_hash=quote_hash(content),
        )
        section = Section(
            id=stable_id("sec", raw_file.id, draft.title, line_start, line_end),
            raw_file_id=raw_file.id,
            title=draft.title,
            section_type=draft.section_type,
            level=draft.level,
            order_index=order_index,
            element_ids=element_ids,
            content=content,
            char_count=len(content),
            source_locator=locator,
            metadata={
                "line_start": line_start,
                "line_end": line_end,
                "line_spans": [span.__dict__ for span in line_spans],
            },
        )
        sections.append(section)

    section_by_element_id = {
        element_id: section.id
        for section in sections
        for element_id in section.element_ids
    }
    for index, element in enumerate(elements):
        elements[index] = element.model_copy(update={"parent_section_id": section_by_element_id.get(element.id)})
    return sections


def _draft_sections(lines: list[LineRecord], suffix: str) -> list[SectionDraft]:
    drafts: list[SectionDraft] = []
    current: SectionDraft | None = None

    for line in lines:
        marker = _heading_marker(line.text, suffix)
        if marker:
            current = SectionDraft(
                title=marker[0],
                level=marker[1],
                section_type=SectionType.section if marker[1] > 1 else SectionType.chapter,
                lines=[],
            )
            drafts.append(current)
            continue
        if current is None:
            current = SectionDraft(title="正文", level=1, section_type=SectionType.section, lines=[])
            drafts.append(current)
        current.lines.append(line)

    if len(drafts) == 1 and drafts[0].title == "正文":
        return _window_sections(lines)
    return drafts


def _window_sections(lines: list[LineRecord], max_chars: int = 2400) -> list[SectionDraft]:
    drafts: list[SectionDraft] = []
    current_lines: list[LineRecord] = []
    current_chars = 0
    for line in lines:
        current_lines.append(line)
        current_chars += len(line.text) + 1
        if current_chars >= max_chars:
            title = f"正文 lines {current_lines[0].line_number}-{current_lines[-1].line_number}"
            drafts.append(SectionDraft(title=title, level=1, section_type=SectionType.section, lines=current_lines))
            current_lines = []
            current_chars = 0
    if current_lines:
        title = f"正文 lines {current_lines[0].line_number}-{current_lines[-1].line_number}"
        drafts.append(SectionDraft(title=title, level=1, section_type=SectionType.section, lines=current_lines))
    return drafts


def _heading_marker(line: str, suffix: str) -> tuple[str, int] | None:
    stripped = line.strip()
    if not stripped:
        return None
    if suffix in {".md", ".markdown", "md", "markdown"}:
        match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if match:
            return match.group(2).strip(), len(match.group(1))
    if len(stripped) <= 48 and re.match(r"^(绪论|第[一二三四五六七八九十百0-9]+[章节篇]|[一二三四五六七八九十]+、)", stripped):
        level = 1 if stripped == "绪论" or re.match(r"^第[一二三四五六七八九十百0-9]+章", stripped) else 2
        return stripped, level
    return None


def _compose_section_content(
    lines: list[LineRecord],
    element_by_line: dict[int, DocumentElement],
) -> tuple[str, list[LineSpan]]:
    parts: list[str] = []
    spans: list[LineSpan] = []
    cursor = 0

    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        if parts:
            parts.append("\n")
            cursor += 1
        start = cursor
        parts.append(text)
        cursor += len(text)
        element = element_by_line.get(line.line_number)
        spans.append(
            LineSpan(
                line_start=line.line_number,
                line_end=line.line_number,
                start=start,
                end=cursor,
                element_ids=[element.id] if element else [],
            )
        )
    return "".join(parts), spans


def _build_chunks(raw_file: RawFile, sections: list[Section]) -> list[Chunk]:
    chunks: list[Chunk] = []
    order_index = 0
    for section in sections:
        start = 0
        text = section.content
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(_build_chunk(raw_file, section, chunk_text, start, end, order_index))
                order_index += 1
            if end == len(text):
                break
            start = max(0, end - CHUNK_OVERLAP)
    return chunks


def _build_chunk(
    raw_file: RawFile,
    section: Section,
    text: str,
    char_start: int,
    char_end: int,
    order_index: int,
) -> Chunk:
    line_spans = [LineSpan(**span) for span in section.metadata["line_spans"]]
    overlapping = [span for span in line_spans if span.start < char_end and span.end > char_start] or line_spans[:1]
    line_start = overlapping[0].line_start
    line_end = overlapping[-1].line_end
    element_ids = list(dict.fromkeys(element_id for span in overlapping for element_id in span.element_ids))
    locator = SourceLocator(
        raw_file_id=raw_file.id,
        source_path=raw_file.storage_path,
        source_type=raw_file.source_type,
        locator_text=f"{raw_file.title} lines {line_start}-{line_end}, chars {char_start}-{char_end}",
        line_start=line_start,
        line_end=line_end,
        char_start=char_start,
        char_end=char_end,
        element_ids=element_ids,
        quote_hash=quote_hash(text),
    )
    return Chunk(
        id=stable_id("chunk", raw_file.id, section.id, char_start, char_end),
        raw_file_id=raw_file.id,
        section_id=section.id,
        text=text,
        order_index=order_index,
        char_start=char_start,
        char_end=char_end,
        char_count=len(text),
        source_locator=locator,
        metadata={"section_title": section.title, "line_start": line_start, "line_end": line_end},
    )
