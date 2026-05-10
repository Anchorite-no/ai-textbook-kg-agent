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


@dataclass(frozen=True)
class UnitRecord:
    index: int
    title: str
    text: str
    element_type: DocumentElementType
    locator_text: str
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    slide_number: int | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class UnitSpan:
    start: int
    end: int
    unit: UnitRecord
    element_id: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_raw_file(file_path: Path, original_filename: str | None, file_format: str, text_char_count: int) -> RawFile:
    digest = sha256_file(file_path)
    filename = original_filename or file_path.name
    return RawFile(
        id=f"raw_{digest[:16]}",
        original_filename=filename,
        title=Path(filename).stem,
        format=file_format,
        source_type="uploaded",
        storage_path=str(file_path),
        sha256=digest,
        size_bytes=file_path.stat().st_size,
        text_char_count=text_char_count,
        metadata={"parser": "multi_format_parser"},
    )


def build_parsed_from_units(
    raw_file: RawFile,
    units: list[UnitRecord],
    section_strategy: str,
) -> ParsedTextbook:
    elements = _build_elements(raw_file, units)
    sections = _build_sections(raw_file, units, elements)
    chunks = _build_chunks(raw_file, sections)
    parsed = ParsedTextbook(
        id=stable_id("parsed", raw_file.id, raw_file.sha256, section_strategy),
        raw_file=raw_file,
        elements=elements,
        sections=sections,
        chunks=chunks,
        metadata={
            "source_pipeline": raw_file.metadata.get("parser", "multi_format_parser"),
            "section_strategy": section_strategy,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "element_count": len(elements),
            "section_count": len(sections),
            "chunk_count": len(chunks),
        },
    )
    return parsed


def save_parsed(parsed: ParsedTextbook) -> Path:
    output_path = settings.parsed_data_dir / f"{parsed.raw_file.id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(parsed.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def source_locator(raw_file: RawFile, unit: UnitRecord, text: str, element_ids: list[str] | None = None) -> SourceLocator:
    return SourceLocator(
        raw_file_id=raw_file.id,
        source_path=raw_file.storage_path,
        source_type=raw_file.source_type,
        locator_text=unit.locator_text,
        page_start=unit.page,
        page_end=unit.page,
        line_start=unit.line_start,
        line_end=unit.line_end,
        sheet_name=unit.sheet_name,
        row_start=unit.row_start,
        row_end=unit.row_end,
        slide_number=unit.slide_number,
        element_ids=element_ids or [],
        quote_hash=quote_hash(text),
    )


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def chunk_text(raw_file: RawFile, section: Section, text: str, order_start: int) -> tuple[list[Chunk], int]:
    chunks: list[Chunk] = []
    start = 0
    order_index = order_start
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk_body = text[start:end].strip()
        if chunk_body:
            locator = section.source_locator.model_copy(
                update={
                    "char_start": start,
                    "char_end": end,
                    "quote_hash": quote_hash(chunk_body),
                }
            )
            chunks.append(
                Chunk(
                    id=stable_id("chunk", raw_file.id, section.id, start, end),
                    raw_file_id=raw_file.id,
                    section_id=section.id,
                    text=chunk_body,
                    order_index=order_index,
                    char_start=start,
                    char_end=end,
                    char_count=len(chunk_body),
                    source_locator=locator,
                    metadata={"section_title": section.title},
                )
            )
            order_index += 1
        if end == len(text):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return chunks, order_index


def _build_elements(raw_file: RawFile, units: list[UnitRecord]) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    for unit in units:
        text = clean_text(unit.text)
        if not text:
            continue
        locator = source_locator(raw_file, unit, text)
        elements.append(
            DocumentElement(
                id=stable_id("elem", raw_file.id, unit.index, unit.locator_text),
                raw_file_id=raw_file.id,
                type=unit.element_type,
                text=text,
                order_index=len(elements),
                source_locator=locator,
                char_count=len(text),
                metadata=unit.metadata or {},
            )
        )
    return elements


def _build_sections(raw_file: RawFile, units: list[UnitRecord], elements: list[DocumentElement]) -> list[Section]:
    element_by_key = {
        (element.source_locator.locator_text, element.order_index): element
        for element in elements
    }
    sections: list[Section] = []

    for element in elements:
        unit = _unit_for_element(units, element)
        title = unit.title or element.source_locator.locator_text
        locator = element.source_locator.model_copy(update={"element_ids": [element.id]})
        section = Section(
            id=stable_id("sec", raw_file.id, title, element.id),
            raw_file_id=raw_file.id,
            title=title,
            section_type=_section_type_for_unit(unit),
            level=1,
            order_index=len(sections),
            element_ids=[element.id],
            content=element.text,
            char_count=len(element.text),
            source_locator=locator,
            metadata={
                "unit_index": unit.index,
                "unit_title": unit.title,
                **(unit.metadata or {}),
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


def _unit_for_element(units: list[UnitRecord], element: DocumentElement) -> UnitRecord:
    for unit in units:
        if unit.locator_text == element.source_locator.locator_text:
            return unit
    raise ValueError(f"Cannot find source unit for element: {element.id}")


def _section_type_for_unit(unit: UnitRecord) -> SectionType:
    if unit.slide_number is not None:
        return SectionType.slide
    if unit.sheet_name is not None:
        return SectionType.sheet
    if unit.page is not None:
        return SectionType.page_window
    return SectionType.section


def _build_chunks(raw_file: RawFile, sections: list[Section]) -> list[Chunk]:
    chunks: list[Chunk] = []
    order_index = 0
    for section in sections:
        section_chunks, order_index = chunk_text(raw_file, section, section.content, order_index)
        chunks.extend(section_chunks)
    return chunks
