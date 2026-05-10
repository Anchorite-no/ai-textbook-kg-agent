from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from app.models.schemas import DocumentElementType, ParsedTextbook
from app.services.parser_utils import (
    UnitRecord,
    build_parsed_from_units,
    build_raw_file,
    clean_text,
    save_parsed,
)
from app.services.text_file_parser import SUPPORTED_TEXT_EXTENSIONS, parse_uploaded_text_file


SUPPORTED_UPLOAD_EXTENSIONS = {
    *SUPPORTED_TEXT_EXTENSIONS,
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".pptx",
}


def parse_uploaded_file(file_path: Path, original_filename: str | None = None) -> tuple[ParsedTextbook, Path]:
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_TEXT_EXTENSIONS:
        return parse_uploaded_text_file(file_path, original_filename=original_filename)
    if suffix == ".pdf":
        parsed = _parse_pdf(file_path, original_filename)
    elif suffix == ".docx":
        parsed = _parse_docx(file_path, original_filename)
    elif suffix == ".xlsx":
        parsed = _parse_xlsx(file_path, original_filename)
    elif suffix == ".csv":
        parsed = _parse_csv(file_path, original_filename)
    elif suffix == ".pptx":
        parsed = _parse_pptx(file_path, original_filename)
    else:
        raise ValueError(f"当前计划 02 暂不支持 {suffix or 'unknown'}，请先上传 txt/md/pdf/docx/xlsx/csv/pptx")
    return parsed, save_parsed(parsed)


def _parse_pdf(file_path: Path, original_filename: str | None) -> ParsedTextbook:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 pypdf 依赖，请先安装 backend/requirements.txt") from exc

    reader = PdfReader(str(file_path))
    units: list[UnitRecord] = []
    total_chars = 0
    title = Path(original_filename or file_path.name).stem

    for index, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        total_chars += len(text)
        if not text:
            continue
        units.append(
            UnitRecord(
                index=index,
                title=f"Page {index}",
                text=text,
                element_type=DocumentElementType.page,
                locator_text=f"{title} page {index}",
                page=index,
                metadata={"page": index},
            )
        )

    raw_file = build_raw_file(file_path, original_filename, "pdf", total_chars)
    raw_file = raw_file.model_copy(update={"page_count": len(reader.pages)})
    return build_parsed_from_units(raw_file, units, "pdf_pages")


def _parse_docx(file_path: Path, original_filename: str | None) -> ParsedTextbook:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 python-docx 依赖，请先安装 backend/requirements.txt") from exc

    document = Document(str(file_path))
    title = Path(original_filename or file_path.name).stem
    blocks = _docx_blocks(document)
    units: list[UnitRecord] = []
    current_title = "正文"
    current_lines: list[str] = []
    current_start = 1
    unit_index = 1

    def flush(end_line: int) -> None:
        nonlocal unit_index, current_lines, current_start, current_title
        text = clean_text("\n".join(current_lines))
        if not text:
            current_lines = []
            return
        units.append(
            UnitRecord(
                index=unit_index,
                title=current_title,
                text=text,
                element_type=DocumentElementType.paragraph,
                locator_text=f"{title} paragraphs {current_start}-{end_line}",
                line_start=current_start,
                line_end=end_line,
                metadata={"paragraph_start": current_start, "paragraph_end": end_line},
            )
        )
        unit_index += 1
        current_lines = []

    for line_number, kind, text, style in blocks:
        is_heading = kind == "paragraph" and style.lower().startswith("heading")
        if is_heading:
            flush(line_number - 1)
            current_title = clean_text(text) or f"Heading {line_number}"
            current_start = line_number
            continue
        current_lines.append(text)
    flush(blocks[-1][0] if blocks else 1)

    raw_file = build_raw_file(file_path, original_filename, "docx", sum(len(unit.text) for unit in units))
    return build_parsed_from_units(raw_file, units, "docx_headings")


def _docx_blocks(document: object) -> list[tuple[int, str, str, str]]:
    blocks: list[tuple[int, str, str, str]] = []
    line_number = 1
    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text)
        if text:
            blocks.append((line_number, "paragraph", text, paragraph.style.name if paragraph.style else ""))
            line_number += 1
    for table_index, table in enumerate(document.tables, start=1):
        table_text = _markdown_table([[cell.text for cell in row.cells] for row in table.rows])
        if table_text:
            blocks.append((line_number, "table", table_text, f"Table {table_index}"))
            line_number += 1
    return blocks


def _parse_xlsx(file_path: Path, original_filename: str | None) -> ParsedTextbook:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 openpyxl 依赖，请先安装 backend/requirements.txt") from exc

    workbook = load_workbook(str(file_path), read_only=True, data_only=True)
    title = Path(original_filename or file_path.name).stem
    units: list[UnitRecord] = []
    unit_index = 1
    for sheet in workbook.worksheets:
        rows = [(row_index, ["" if value is None else str(value) for value in row]) for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1)]
        non_empty = [(row_index, _trim_empty_tail(values)) for row_index, values in rows if any(str(value).strip() for value in values)]
        for row_group in _chunk_rows(non_empty, 40):
            row_start = row_group[0][0]
            row_end = row_group[-1][0]
            table_text = _markdown_table([values for _row_index, values in row_group])
            units.append(
                UnitRecord(
                    index=unit_index,
                    title=f"{sheet.title} rows {row_start}-{row_end}",
                    text=table_text,
                    element_type=DocumentElementType.sheet,
                    locator_text=f"{title} sheet {sheet.title} rows {row_start}-{row_end}",
                    sheet_name=sheet.title,
                    row_start=row_start,
                    row_end=row_end,
                    metadata={"sheet_name": sheet.title, "row_start": row_start, "row_end": row_end},
                )
            )
            unit_index += 1
    workbook.close()

    raw_file = build_raw_file(file_path, original_filename, "xlsx", sum(len(unit.text) for unit in units))
    return build_parsed_from_units(raw_file, units, "xlsx_sheets_rows")


def _parse_csv(file_path: Path, original_filename: str | None) -> ParsedTextbook:
    title = Path(original_filename or file_path.name).stem
    text = _decode_csv(file_path)
    rows = list(csv.reader(text.splitlines()))
    non_empty = [(index, _trim_empty_tail(row)) for index, row in enumerate(rows, start=1) if any(cell.strip() for cell in row)]
    units: list[UnitRecord] = []
    for unit_index, row_group in enumerate(_chunk_rows(non_empty, 40), start=1):
        row_start = row_group[0][0]
        row_end = row_group[-1][0]
        table_text = _markdown_table([values for _row_index, values in row_group])
        units.append(
            UnitRecord(
                index=unit_index,
                title=f"CSV rows {row_start}-{row_end}",
                text=table_text,
                element_type=DocumentElementType.sheet,
                locator_text=f"{title} rows {row_start}-{row_end}",
                sheet_name="CSV",
                row_start=row_start,
                row_end=row_end,
                metadata={"sheet_name": "CSV", "row_start": row_start, "row_end": row_end},
            )
        )

    raw_file = build_raw_file(file_path, original_filename, "csv", sum(len(unit.text) for unit in units))
    return build_parsed_from_units(raw_file, units, "csv_rows")


def _parse_pptx(file_path: Path, original_filename: str | None) -> ParsedTextbook:
    try:
        from pptx import Presentation
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 python-pptx 依赖，请先安装 backend/requirements.txt") from exc

    presentation = Presentation(str(file_path))
    title = Path(original_filename or file_path.name).stem
    units: list[UnitRecord] = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_lines: list[str] = []
        slide_title = f"Slide {slide_number}"
        for shape in sorted(slide.shapes, key=lambda item: (getattr(item, "top", 0), getattr(item, "left", 0))):
            if getattr(shape, "has_text_frame", False):
                text = clean_text(shape.text)
                if text:
                    if slide_title == f"Slide {slide_number}":
                        slide_title = text.splitlines()[0][:80]
                    slide_lines.append(text)
            if getattr(shape, "has_table", False):
                table_rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
                table_text = _markdown_table(table_rows)
                if table_text:
                    slide_lines.append(table_text)
        text = clean_text("\n".join(slide_lines))
        if not text:
            continue
        units.append(
            UnitRecord(
                index=slide_number,
                title=slide_title,
                text=text,
                element_type=DocumentElementType.slide,
                locator_text=f"{title} slide {slide_number}",
                slide_number=slide_number,
                metadata={"slide_number": slide_number},
            )
        )

    raw_file = build_raw_file(file_path, original_filename, "pptx", sum(len(unit.text) for unit in units))
    raw_file = raw_file.model_copy(update={"page_count": len(presentation.slides)})
    return build_parsed_from_units(raw_file, units, "pptx_slides")


def _decode_csv(file_path: Path) -> str:
    raw = file_path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _chunk_rows(rows: list[tuple[int, list[str]]], size: int) -> Iterable[list[tuple[int, list[str]]]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def _trim_empty_tail(values: list[str]) -> list[str]:
    trimmed = list(values)
    while trimmed and not str(trimmed[-1]).strip():
        trimmed.pop()
    return [clean_text(str(value)) for value in trimmed]


def _markdown_table(rows: list[list[str]]) -> str:
    clean_rows = [[clean_text(cell) for cell in row] for row in rows if any(clean_text(cell) for cell in row)]
    if not clean_rows:
        return ""
    width = max(len(row) for row in clean_rows)
    padded = [row + [""] * (width - len(row)) for row in clean_rows]
    header = padded[0]
    body = padded[1:] or [[""] * width]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)
