from __future__ import annotations

import io
from pathlib import Path


def extract_document_text(data: bytes | None, filename: str) -> tuple[str | None, str | None]:
    """Return (text, error).

    text is None and error is None when the type has no text extractor (compare by hash only).
    """
    if data is None:
        return None, "file not found"
    ext = Path(filename or "").suffix.lower()
    try:
        if ext in {".txt", ".csv", ".rtf"}:
            return data.decode("utf-8", errors="replace"), None
        if ext == ".docx":
            return _docx_text(data), None
        if ext == ".xlsx":
            return _xlsx_text(data), None
        if ext == ".pdf":
            return _pdf_text(data), None
    except Exception as exc:
        return None, str(exc)[:300]
    return None, None


def _docx_text(data: bytes) -> str:
    """Emit paragraphs and table cells in document order, one non-empty cell per line."""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(data))
    lines: list[str] = []

    def add_text(text: str) -> None:
        text = (text or "").strip()
        if text:
            lines.append(text)

    def unique_row_cells(row):
        cells = []
        for cell in row.cells:
            if not cells or cell._tc is not cells[-1]._tc:
                cells.append(cell)
        return cells

    def add_table(table) -> None:
        for row in table.rows:
            for cell in unique_row_cells(row):
                nested = list(cell.tables)
                if nested:
                    for nested_table in nested:
                        add_table(nested_table)
                    continue
                add_text(cell.text)

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            add_text(Paragraph(child, doc).text)
        elif child.tag == qn("w:tbl"):
            add_table(Table(child, doc))
    return "\n".join(lines)


def _xlsx_text(data: bytes) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    try:
        lines: list[str] = []
        for sheet in workbook.worksheets:
            lines.append(f"# {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    lines.append("\t".join(values))
        return "\n".join(lines)
    finally:
        workbook.close()


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(part for part in parts if part)
