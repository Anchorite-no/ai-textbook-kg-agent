from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


CHUNK_SIZE = 700
CHUNK_OVERLAP = 80
SECTION_PAGE_WINDOW = 5


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    text_file: str
    image_file: str | None


@dataclass(frozen=True)
class PageSpan:
    page: int
    start: int
    end: int
    element_id: str


@dataclass
class SectionDraft:
    title: str
    level: int
    section_type: SectionType
    chapter_title: str | None = None
    parent_title: str | None = None
    page_lines: list[tuple[int, str]] | None = None

    def __post_init__(self) -> None:
        if self.page_lines is None:
            self.page_lines = []

    def add_line(self, page: int, line: str) -> None:
        self.page_lines.append((page, line))


@dataclass(frozen=True)
class HeadingMarker:
    title: str
    level: int
    section_type: SectionType


def stable_id(prefix: str, *parts: object) -> str:
    joined = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def quote_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def dump_model_json(path: Path, model: ParsedTextbook) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def import_converted_textbook(
    textbook_title: str | None = None,
    converted_root: Path | None = None,
    parsed_output_dir: Path | None = None,
) -> tuple[ParsedTextbook, Path]:
    converted_root = converted_root or settings.converted_textbooks_dir
    parsed_output_dir = parsed_output_dir or settings.parsed_data_dir
    manifest = _load_manifest(converted_root)
    book_record = _select_book(manifest, textbook_title)
    book_dir = converted_root / _safe_name(book_record["title"])

    raw_file_id = f"raw_{book_record['source_sha256_16']}"
    raw_file = RawFile(
        id=raw_file_id,
        original_filename=Path(book_record["source_pdf"]).name,
        title=book_record["title"],
        format="pdf",
        source_type="converted_textbook",
        storage_path=str(book_dir),
        sha256=book_record["source_sha256_16"],
        size_bytes=int(book_record.get("source_size_bytes") or 0),
        page_count=int(book_record.get("pages") or 0),
        text_char_count=int(book_record.get("text_chars") or 0),
        metadata={
            "source_pdf": book_record.get("source_pdf"),
            "pdf_metadata": book_record.get("pdf_metadata") or {},
            "converted_outputs": book_record.get("outputs") or {},
        },
    )

    pages = _read_pages(book_dir, book_record)
    elements = _build_page_elements(raw_file, pages)
    sections = _build_sections(raw_file, pages, elements)
    chunks = _build_chunks(raw_file, sections)

    parsed = ParsedTextbook(
        id=stable_id("parsed", raw_file.id, raw_file.sha256),
        raw_file=raw_file,
        elements=elements,
        sections=sections,
        chunks=chunks,
        metadata={
            "source_pipeline": "materials.converted_textbooks",
            "section_strategy": sections[0].metadata.get("structure_strategy", "page_window") if sections else "none",
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "section_page_window": SECTION_PAGE_WINDOW,
            "element_count": len(elements),
            "section_count": len(sections),
            "chunk_count": len(chunks),
        },
    )
    output_path = parsed_output_dir / f"{raw_file.id}.json"
    dump_model_json(output_path, parsed)
    return parsed, output_path


def _load_manifest(converted_root: Path) -> dict[str, Any]:
    manifest_path = converted_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Converted textbook manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _select_book(manifest: dict[str, Any], textbook_title: str | None) -> dict[str, Any]:
    books = manifest.get("books") or []
    if not books:
        raise ValueError("No books found in converted textbook manifest.")
    if textbook_title:
        normalized = textbook_title.strip().lower()
        for book in books:
            title = str(book.get("title", "")).lower()
            source_name = Path(str(book.get("source_pdf", ""))).stem.lower()
            if normalized in {title, source_name} or normalized in title:
                return book
        raise ValueError(f"Converted textbook not found: {textbook_title}")
    return books[0]


def _read_pages(book_dir: Path, book_record: dict[str, Any]) -> list[PageText]:
    pages: list[PageText] = []
    for record in book_record.get("page_records") or []:
        text_file = str(record["text_file"])
        text_path = book_dir / text_file
        text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
        pages.append(
            PageText(
                page=int(record["page"]),
                text=_normalize_text(text),
                text_file=text_file,
                image_file=record.get("image_file"),
            )
        )
    return pages


def _normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [_clean_line(line) for line in text.split("\n")]
    return "\n".join(line for line in lines if line or lines).strip()


def _build_page_elements(raw_file: RawFile, pages: list[PageText]) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    for order_index, page in enumerate(pages):
        element_id = stable_id("elem", raw_file.id, "page", page.page)
        source_locator = SourceLocator(
            raw_file_id=raw_file.id,
            source_path=raw_file.metadata.get("source_pdf") or raw_file.storage_path,
            source_type=raw_file.source_type,
            locator_text=f"{raw_file.title} page {page.page}",
            page_start=page.page,
            page_end=page.page,
            quote_hash=quote_hash(page.text),
        )
        elements.append(
            DocumentElement(
                id=element_id,
                raw_file_id=raw_file.id,
                type=DocumentElementType.page,
                text=page.text,
                order_index=order_index,
                source_locator=source_locator,
                char_count=len(page.text),
                metadata={
                    "page": page.page,
                    "text_file": page.text_file,
                    "image_file": page.image_file,
                },
            )
        )
    return elements


def _build_sections(
    raw_file: RawFile,
    pages: list[PageText],
    elements: list[DocumentElement],
) -> list[Section]:
    structured = _build_structured_sections(raw_file, pages, elements)
    sections = structured if len(structured) >= 3 else _build_page_window_sections(raw_file, pages, elements)

    section_by_element_id = {
        element_id: section.id
        for section in sections
        for element_id in section.element_ids
    }
    for index, element in enumerate(elements):
        elements[index] = element.model_copy(
            update={"parent_section_id": section_by_element_id.get(element.id)}
        )
    return sections


def _build_page_window_sections(
    raw_file: RawFile,
    pages: list[PageText],
    elements: list[DocumentElement],
) -> list[Section]:
    sections: list[Section] = []
    element_by_page = {element.metadata["page"]: element for element in elements}

    for order_index, page_group in enumerate(_group_pages(pages, SECTION_PAGE_WINDOW)):
        page_start = page_group[0].page
        page_end = page_group[-1].page
        section_id = stable_id("sec", raw_file.id, "pages", page_start, page_end)
        page_spans, content = _compose_section_content(page_group, element_by_page)
        element_ids = [span.element_id for span in page_spans]
        title = _infer_section_title(page_group, page_start, page_end)
        source_locator = SourceLocator(
            raw_file_id=raw_file.id,
            source_path=raw_file.metadata.get("source_pdf") or raw_file.storage_path,
            source_type=raw_file.source_type,
            locator_text=f"{raw_file.title} pages {page_start}-{page_end}",
            page_start=page_start,
            page_end=page_end,
            element_ids=element_ids,
            quote_hash=quote_hash(content),
        )
        section = Section(
            id=section_id,
            raw_file_id=raw_file.id,
            title=title,
            section_type=SectionType.page_window,
            level=1,
            order_index=order_index,
            element_ids=element_ids,
            content=content,
            char_count=len(content),
            source_locator=source_locator,
            metadata={
                "page_start": page_start,
                "page_end": page_end,
                "page_spans": [span.__dict__ for span in page_spans],
            },
        )
        sections.append(section)
    return sections


def _build_structured_sections(
    raw_file: RawFile,
    pages: list[PageText],
    elements: list[DocumentElement],
) -> list[Section]:
    cleaned_pages = [(page, _clean_page_lines(page.text)) for page in pages]
    start_index = _find_body_start(cleaned_pages)
    if start_index is None:
        return []

    drafts: list[SectionDraft] = []
    current: SectionDraft | None = None
    current_chapter: str | None = None
    current_parent: str | None = None

    def start_draft(marker: HeadingMarker) -> SectionDraft:
        parent_title = current_parent if marker.level > 2 else current_chapter if marker.level > 1 else None
        draft = SectionDraft(
            title=_compose_section_title(current_chapter, current_parent, marker),
            level=marker.level,
            section_type=marker.section_type,
            chapter_title=current_chapter if marker.level > 1 else marker.title,
            parent_title=parent_title,
        )
        drafts.append(draft)
        return draft

    for page, lines in cleaned_pages[start_index:]:
        if _is_toc_page(lines):
            continue
        for line_index, line in enumerate(lines):
            if not line:
                continue
            marker = _extract_heading_marker(line)
            if marker is not None:
                if marker.level == 1:
                    if current_chapter == marker.title and line_index <= 1:
                        continue
                    current_chapter = marker.title
                    current_parent = None
                elif marker.level == 2:
                    current_parent = marker.title
                if _is_duplicate_running_heading(marker, current, line_index):
                    continue
                current = start_draft(marker)
                continue
            if _is_noise_line(line, raw_file.title, current_chapter, line_index):
                continue
            if current is None:
                marker = HeadingMarker(
                    title=f"正文 page {page.page}",
                    level=1,
                    section_type=SectionType.section,
                )
                current = start_draft(marker)
            current.add_line(page.page, line)

    return _materialize_section_drafts(raw_file, drafts, elements, start_index)


def _materialize_section_drafts(
    raw_file: RawFile,
    drafts: list[SectionDraft],
    elements: list[DocumentElement],
    body_start_index: int,
) -> list[Section]:
    sections: list[Section] = []
    element_by_page = {element.metadata["page"]: element for element in elements}
    skipped_empty = 0

    for draft in drafts:
        if not draft.page_lines:
            skipped_empty += 1
            continue
        page_spans, content = _compose_content_from_page_lines(draft.page_lines, element_by_page)
        content = content.strip()
        if not content:
            skipped_empty += 1
            continue
        page_start = page_spans[0].page
        page_end = page_spans[-1].page
        element_ids = list(dict.fromkeys(span.element_id for span in page_spans))
        section_id = stable_id("sec", raw_file.id, draft.title, page_start, page_end)
        source_locator = SourceLocator(
            raw_file_id=raw_file.id,
            source_path=raw_file.metadata.get("source_pdf") or raw_file.storage_path,
            source_type=raw_file.source_type,
            locator_text=f"{raw_file.title} pages {page_start}-{page_end}",
            page_start=page_start,
            page_end=page_end,
            element_ids=element_ids,
            quote_hash=quote_hash(content),
        )
        sections.append(
            Section(
                id=section_id,
                raw_file_id=raw_file.id,
                title=draft.title,
                section_type=draft.section_type,
                level=draft.level,
                order_index=len(sections),
                element_ids=element_ids,
                content=content,
                char_count=len(content),
                source_locator=source_locator,
                metadata={
                    "page_start": page_start,
                    "page_end": page_end,
                    "page_spans": [span.__dict__ for span in page_spans],
                    "heading_level": draft.level,
                    "chapter_title": draft.chapter_title,
                    "parent_title": draft.parent_title,
                    "body_start_page_index": body_start_index,
                    "skipped_empty_heading_count": skipped_empty,
                    "structure_strategy": "heading_detection",
                },
            )
        )
    return sections


def _group_pages(pages: list[PageText], window: int) -> list[list[PageText]]:
    return [pages[index : index + window] for index in range(0, len(pages), window)]


def _clean_page_lines(text: str) -> list[str]:
    cleaned = [_clean_line(line) for line in text.splitlines()]
    lines: list[str] = []
    previous_blank = False
    for line in cleaned:
        if not line:
            if not previous_blank:
                lines.append("")
            previous_blank = True
            continue
        lines.append(line)
        previous_blank = False
    return lines


def _clean_line(line: str) -> str:
    line = line.replace("\ufeff", "")
    line = line.replace("\u2002", " ").replace("\u2003", " ").replace("\u2005", " ")
    line = line.replace("\u200a", " ").replace("\u00a0", " ").replace("\u3000", " ")
    line = line.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    line = line.replace("�", "")
    line = re.sub(r"[.．·・]{4,}", " ", line)
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", line)
    line = re.sub(r"\s+([，。；：！？、）])", r"\1", line)
    line = re.sub(r"([（《])\s+", r"\1", line)
    return line.strip()


def _find_body_start(cleaned_pages: list[tuple[PageText, list[str]]]) -> int | None:
    for index, (_page, lines) in enumerate(cleaned_pages):
        if _is_toc_page(lines):
            continue
        non_empty = [line for line in lines if line]
        if not non_empty:
            continue
        for line in non_empty[:6]:
            marker = _extract_heading_marker(line)
            if marker is not None and marker.level == 1:
                return index
    return None


def _is_toc_page(lines: list[str]) -> bool:
    non_empty = [line for line in lines if line]
    if not non_empty:
        return False
    if any(line == "目录" for line in non_empty[:5]):
        return True
    toc_like_count = 0
    for line in non_empty:
        heading = _normalize_heading_text(line)
        if re.match(r"^(绪论|第[一二三四五六七八九十百0-9]+[章节篇]|[一二三四五六七八九十]+、).*\d{1,4}$", heading):
            toc_like_count += 1
    return toc_like_count >= 4


def _extract_heading_marker(line: str) -> HeadingMarker | None:
    heading = _normalize_heading_text(line)
    if not heading or len(heading) > 48:
        return None

    if re.fullmatch(r"绪论", heading):
        return HeadingMarker(title="绪论", level=1, section_type=SectionType.chapter)

    chapter = re.match(r"^(第[一二三四五六七八九十百0-9]+章)(.+)?$", heading)
    if chapter:
        title = _format_heading(chapter.group(1), chapter.group(2))
        return HeadingMarker(title=title, level=1, section_type=SectionType.chapter)

    section = re.match(r"^(第[一二三四五六七八九十百0-9]+节)(.+)?$", heading)
    if section:
        title = _format_heading(section.group(1), section.group(2))
        return HeadingMarker(title=title, level=2, section_type=SectionType.section)

    numbered = re.match(r"^([一二三四五六七八九十]+)、(.{2,32})$", heading)
    if numbered:
        title = f"{numbered.group(1)}、{numbered.group(2).strip()}"
        return HeadingMarker(title=title, level=3, section_type=SectionType.section)

    return None


def _normalize_heading_text(line: str) -> str:
    heading = _clean_line(line)
    heading = heading.replace("|", " ")
    heading = re.sub(r"\s+", "", heading)
    heading = heading.strip(" ：:;；")
    return heading


def _format_heading(prefix: str, suffix: str | None) -> str:
    suffix = (suffix or "").strip(" ：:;；|")
    if suffix:
        return f"{prefix} {suffix}"
    return prefix


def _compose_section_title(
    current_chapter: str | None,
    current_parent: str | None,
    marker: HeadingMarker,
) -> str:
    if marker.level == 1 or not current_chapter:
        return marker.title
    if marker.level > 2 and current_parent:
        return f"{current_chapter} / {current_parent} / {marker.title}"
    return f"{current_chapter} / {marker.title}"


def _is_duplicate_running_heading(
    marker: HeadingMarker,
    current: SectionDraft | None,
    line_index: int,
) -> bool:
    return (
        current is not None
        and marker.level == 1
        and current.chapter_title == marker.title
        and line_index <= 1
    )


def _is_noise_line(
    line: str,
    book_title: str,
    current_chapter: str | None,
    line_index: int,
) -> bool:
    if not line:
        return True
    if re.fullmatch(r"\d{1,4}", line):
        return True
    if line in {"本章数字资源", "扫描图片", "体验AR", "本章思维导图"}:
        return True
    if line_index <= 1 and current_chapter and _normalize_heading_text(line) == _normalize_heading_text(current_chapter):
        return True
    title_without_index = re.sub(r"^\d+_", "", book_title)
    if line_index <= 1 and _normalize_heading_text(line) in {
        _normalize_heading_text(book_title),
        _normalize_heading_text(title_without_index),
    }:
        return True
    return False


def _compose_content_from_page_lines(
    page_lines: list[tuple[int, str]],
    element_by_page: dict[int, DocumentElement],
) -> tuple[list[PageSpan], str]:
    by_page: dict[int, list[str]] = {}
    for page, line in page_lines:
        by_page.setdefault(page, []).append(line)

    parts: list[str] = []
    spans: list[PageSpan] = []
    cursor = 0
    for page in sorted(by_page):
        page_content = _join_clean_lines(by_page[page])
        if not page_content:
            continue
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(page_content)
        cursor += len(page_content)
        spans.append(
            PageSpan(
                page=page,
                start=start,
                end=cursor,
                element_id=element_by_page[page].id,
            )
        )
    return spans, "".join(parts)


def _join_clean_lines(lines: list[str]) -> str:
    paragraphs: list[str] = []
    for line in lines:
        if not line:
            continue
        if paragraphs and _should_merge_lines(paragraphs[-1], line):
            paragraphs[-1] = f"{paragraphs[-1]}{line}"
        else:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _should_merge_lines(previous: str, current: str) -> bool:
    if not previous:
        return False
    if re.match(r"^(\d+\.|[（(][一二三四五六七八九十0-9]+[）)]|[一二三四五六七八九十]+、)", current):
        return False
    if previous.endswith(("。", "；", "：", "！", "？", "）", "」", "”")):
        return False
    return True


def _compose_section_content(
    pages: list[PageText],
    element_by_page: dict[int, DocumentElement],
) -> tuple[list[PageSpan], str]:
    parts: list[str] = []
    spans: list[PageSpan] = []
    cursor = 0
    for page in pages:
        prefix = f"第 {page.page} 页\n"
        page_text = f"{prefix}{page.text}".strip()
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(page_text)
        cursor += len(page_text)
        spans.append(
            PageSpan(
                page=page.page,
                start=start,
                end=cursor,
                element_id=element_by_page[page.page].id,
            )
        )
    return spans, "".join(parts)


def _infer_section_title(pages: list[PageText], page_start: int, page_end: int) -> str:
    for page in pages:
        for line in page.text.splitlines():
            candidate = line.strip()
            if _looks_like_heading(candidate):
                return candidate[:80]
    return f"页 {page_start}-{page_end}"


def _looks_like_heading(line: str) -> bool:
    if not line or len(line) > 40:
        return False
    if re.search(r"第[一二三四五六七八九十百0-9]+[章节篇]", line):
        return True
    if re.match(r"^[一二三四五六七八九十]+[、.．]", line):
        return True
    return line in {"绪论", "目录", "前言"}


def _build_chunks(raw_file: RawFile, sections: list[Section]) -> list[Chunk]:
    chunks: list[Chunk] = []
    order_index = 0
    for section in sections:
        text = section.content
        if not text.strip():
            continue
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    _build_chunk(raw_file, section, chunk_text, start, end, order_index)
                )
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
    page_spans = [PageSpan(**span) for span in section.metadata["page_spans"]]
    overlapping = [
        span
        for span in page_spans
        if span.start < char_end and span.end > char_start
    ]
    if not overlapping:
        overlapping = [page_spans[0]]
    page_start = overlapping[0].page
    page_end = overlapping[-1].page
    element_ids = [span.element_id for span in overlapping]
    chunk_id = stable_id("chunk", raw_file.id, section.id, char_start, char_end)
    locator = SourceLocator(
        raw_file_id=raw_file.id,
        source_path=raw_file.metadata.get("source_pdf") or raw_file.storage_path,
        source_type=raw_file.source_type,
        locator_text=f"{raw_file.title} pages {page_start}-{page_end}, chars {char_start}-{char_end}",
        page_start=page_start,
        page_end=page_end,
        char_start=char_start,
        char_end=char_end,
        element_ids=element_ids,
        quote_hash=quote_hash(text),
    )
    return Chunk(
        id=chunk_id,
        raw_file_id=raw_file.id,
        section_id=section.id,
        text=text,
        order_index=order_index,
        char_start=char_start,
        char_end=char_end,
        char_count=len(text),
        source_locator=locator,
        metadata={
            "page_start": page_start,
            "page_end": page_end,
            "section_title": section.title,
        },
    )


def _safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "_", value)
    value = re.sub(r"\s+", "_", value).strip(" ._")
    return value or "document"
